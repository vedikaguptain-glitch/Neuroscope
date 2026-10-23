"""Use continuous risk-rate supervision without changing the binary test target."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from joblib import Parallel, delayed, parallel_backend
from scipy.optimize import minimize
from sklearn.base import clone
from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import VarianceThreshold
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    mean_squared_error,
    roc_auc_score,
)
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from ml.artifacts import artifact_run, resolve_artifact, write_json
from ml.config import DATA_DIR, validate_cv
from ml.records import load_raw_participants, validate_sessions
from ml.utils.advanced_features import AdvancedFeatureView, advanced_features
from ml.utils.features import target_label


@dataclass
class RateCandidate:
    name: str
    estimator: object
    auxiliary: bool = False


def rate_candidates(seed):
    pool = []

    def add(name, model, views=("summary", "rich"), auxiliary=False):
        for view in views:
            pool.append(
                RateCandidate(
                    name + "-" + view + ("-aux" if auxiliary else ""),
                    Pipeline(
                        [
                            ("view", AdvancedFeatureView(view)),
                            ("vectorize", DictVectorizer(sparse=False)),
                            ("variance", VarianceThreshold()),
                            ("scale", StandardScaler()),
                            ("model", clone(model)),
                        ]
                    ),
                    auxiliary,
                )
            )

    for alpha in (0.1, 1.0, 10.0, 100.0, 1000.0):
        add(f"ridge-{alpha}", Ridge(alpha=alpha), views=("summary", "rich", "sequence", "combined"))
    for alpha in (10.0, 100.0, 1000.0):
        add(f"ridge-{alpha}", Ridge(alpha=alpha), auxiliary=True)
    for alpha in (0.001, 0.01, 0.1):
        add(
            f"elastic-{alpha}",
            ElasticNet(alpha=alpha, l1_ratio=0.5, max_iter=5000, random_state=seed),
        )
    for alpha in (0.1, 1.0, 10.0):
        for gamma in (0.001, 0.01):
            add(f"kernel-{alpha}-{gamma}", KernelRidge(alpha=alpha, kernel="rbf", gamma=gamma))
    for components in (2, 5, 10):
        add(f"pls-{components}", PLSRegression(n_components=components, scale=False))
    add(
        "extra-trees",
        ExtraTreesRegressor(
            n_estimators=300, min_samples_leaf=5, max_features=0.5, n_jobs=1, random_state=seed
        ),
    )
    return pool


def _rate(session):
    choices = [
        t["action_taken"] == "gamble" for t in session["trials"] if t["task_id"] == "risk_pref"
    ]
    if len(choices) != 30:
        raise ValueError("Risk-rate experiments require exactly 30 target trials.")
    return float(np.mean(choices))


def _fit(candidate, features, rates, aux_features, aux_rates):
    if candidate.auxiliary:
        features = list(features) + list(aux_features)
        rates = np.r_[rates, aux_rates]
    return clone(candidate.estimator).fit(features, rates)


def _predict(model, features):
    return np.clip(np.asarray(model.predict(features)).reshape(-1), 0.0, 1.0)


def _inner(candidate, features, rates, aux_features, aux_rates, splits):
    total = np.zeros(len(rates))
    counts = np.zeros(len(rates))
    for train, test in splits:
        model = _fit(candidate, [features[i] for i in train], rates[train], aux_features, aux_rates)
        total[test] += _predict(model, [features[i] for i in test])
        counts[test] += 1
    return total / counts


def _weights(matrix, rates):
    losses = np.mean((matrix - rates[:, None]) ** 2, axis=0)
    selected = np.argsort(losses, kind="stable")[: min(15, len(losses))]
    p = matrix[:, selected]
    initial = np.full(len(selected), 1 / len(selected))

    def objective(weights):
        residual = p @ weights - rates
        return float(
            np.mean(residual**2) + 0.001 * np.sum((weights - initial) ** 2)
        ), 2 * p.T @ residual / len(rates) + 0.002 * (weights - initial)

    fit = minimize(
        objective,
        initial,
        jac=True,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * len(selected),
        constraints={"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(len(w))},
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not fit.success:
        raise RuntimeError("Rate ensemble optimization failed.")
    weights = np.zeros(matrix.shape[1])
    weights[selected] = fit.x
    weights[weights < 1e-6] = 0
    return weights / weights.sum()


def _threshold(prediction, labels):
    return float(
        max(
            np.linspace(0.4, 0.6, 17),
            key=lambda t: (accuracy_score(labels, prediction >= t), -abs(t - 0.5)),
        )
    )


@dataclass
class RatePredictor:
    models: list
    weights: np.ndarray
    threshold: float

    def predict_rate(self, sessions):
        features = [advanced_features(s) for s in sessions]
        return np.column_stack([_predict(m, features) for m in self.models]) @ self.weights

    def predict(self, sessions):
        return (self.predict_rate(sessions) >= self.threshold).astype(int)


def run_rate_benchmark(
    *,
    sessions=None,
    auxiliary_sessions=None,
    seed=42,
    outer_folds=5,
    inner_folds=3,
    repeats=2,
    jobs=4,
    output_dir=None,
    pool=None,
):
    sessions = list(sessions) if sessions is not None else load_raw_participants()
    validate_sessions(sessions)
    identities = {s["participant_id"] for s in sessions}
    auxiliary = list(auxiliary_sessions or [])
    if auxiliary:
        validate_sessions(auxiliary)
    auxiliary = [s for s in auxiliary if s["participant_id"] not in identities]
    rates = np.array([_rate(s) for s in sessions])
    aux_rates = np.array([_rate(s) for s in auxiliary])
    labels = np.array([target_label(s, "risk_pref") for s in sessions])
    validate_cv(labels, outer_folds, inner_folds, jobs)
    if repeats < 1:
        raise ValueError("Inner repeats must be positive.")
    features = [advanced_features(s) for s in sessions]
    aux_features = [advanced_features(s) for s in auxiliary]
    pool = pool if pool is not None else rate_candidates(seed)
    if not auxiliary:
        pool = [c for c in pool if not c.auxiliary]
    prediction = {
        name: np.zeros(len(labels), dtype=int) for name in ("rate_ensemble", "best_rate_model")
    }
    scores = {name: np.zeros(len(labels)) for name in prediction}
    fold_ids = np.zeros(len(labels), dtype=int)
    folds = []
    with threadpool_limits(limits=1), parallel_backend("loky", inner_max_num_threads=1):
        for fold, (train, test) in enumerate(
            StratifiedKFold(outer_folds, shuffle=True, random_state=seed).split(
                np.zeros(len(labels)), labels
            ),
            1,
        ):
            training = [features[i] for i in train]
            testing = [features[i] for i in test]
            splits = list(
                RepeatedStratifiedKFold(
                    n_splits=inner_folds, n_repeats=repeats, random_state=seed
                ).split(np.zeros(len(train)), labels[train])
            )
            matrix = np.column_stack(
                Parallel(n_jobs=jobs)(
                    delayed(_inner)(c, training, rates[train], aux_features, aux_rates, splits)
                    for c in pool
                )
            )
            weights = _weights(matrix, rates[train])
            threshold = _threshold(matrix @ weights, labels[train])
            best = max(
                range(len(pool)),
                key=lambda i: (
                    accuracy_score(labels[train], matrix[:, i] >= 0.5),
                    -mean_squared_error(rates[train], matrix[:, i]),
                ),
            )
            needed = sorted(set(np.flatnonzero(weights).tolist() + [best]))
            test_rates = {}
            for i in needed:
                test_rates[i] = _predict(
                    _fit(pool[i], training, rates[train], aux_features, aux_rates), testing
                )
            ensemble = sum(weights[i] * test_rates[i] for i in needed if weights[i] > 0)
            scores["rate_ensemble"][test] = ensemble
            prediction["rate_ensemble"][test] = (ensemble >= threshold).astype(int)
            scores["best_rate_model"][test] = test_rates[best]
            prediction["best_rate_model"][test] = (test_rates[best] >= 0.5).astype(int)
            fold_ids[test] = fold
            row = {
                "fold": fold,
                "threshold": threshold,
                "weights": {pool[i].name: float(w) for i, w in enumerate(weights) if w > 0},
                "selected_single": pool[best].name,
                "accuracy": {
                    name: float(accuracy_score(labels[test], p[test]))
                    for name, p in prediction.items()
                },
            }
            folds.append(row)
            print(f"[rate-benchmark] fold={fold} accuracy={row['accuracy']}", flush=True)
        splits = list(
            RepeatedStratifiedKFold(
                n_splits=inner_folds, n_repeats=repeats, random_state=seed
            ).split(np.zeros(len(labels)), labels)
        )
        matrix = np.column_stack(
            Parallel(n_jobs=jobs)(
                delayed(_inner)(c, features, rates, aux_features, aux_rates, splits) for c in pool
            )
        )
        weights = _weights(matrix, rates)
        threshold = _threshold(matrix @ weights, labels)
        selected = np.flatnonzero(weights)
        models = [_fit(pool[i], features, rates, aux_features, aux_rates) for i in selected]
    metrics = {
        name: {
            "accuracy": float(accuracy_score(labels, p)),
            "balanced_accuracy": float(balanced_accuracy_score(labels, p)),
            "auc": float(roc_auc_score(labels, scores[name])),
            "correct": int((p == labels).sum()),
            "n": len(labels),
        }
        for name, p in prediction.items()
    }
    result = {
        "primary_arm": "rate_ensemble",
        "target_accuracy": 0.85,
        "target_met": metrics["rate_ensemble"]["accuracy"] >= 0.85,
        "protocol": "Same binary whole-cohort target; training uses continuous gamble rates from training participants only.",
        "n_participants": len(labels),
        "n_auxiliary_training_only": len(auxiliary),
        "candidate_count": len(pool),
        "metrics": metrics,
        "folds": folds,
        "seed": seed,
        "outer_folds": outer_folds,
        "inner_folds": inner_folds,
        "inner_repeats": repeats,
        "data_sha256": hashlib.sha256(
            json.dumps(sessions, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "deployment_weights": {pool[i].name: float(weights[i]) for i in selected},
        "deployment_threshold": threshold,
        "limitation": "Exploratory development on a previously inspected cohort, requiring confirmation on new participants.",
    }
    root = Path(output_dir) if output_dir else DATA_DIR / "optimization_risk_rate"
    rows = [
        {
            "participant_hash": hashlib.sha256(s["participant_id"].encode()).hexdigest(),
            "fold": int(fold_ids[i]),
            "observed": int(labels[i]),
            "predictions": {name: int(p[i]) for name, p in prediction.items()},
        }
        for i, s in enumerate(sessions)
    ]
    with artifact_run(root) as published:
        write_json(published / "results.json", result)
        write_json(published / "predictions.json", rows)
        joblib.dump(
            RatePredictor(models, weights[selected], threshold), published / "predictor.joblib"
        )
    print(f"[rate-benchmark] FINAL {metrics}; target_met={result['target_met']}", flush=True)
    return result


def predict_rates(path, sessions):
    return joblib.load(resolve_artifact(Path(path))).predict(sessions)
