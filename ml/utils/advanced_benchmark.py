"""Fixed, resumable nested benchmark for the unchanged cross-task risk target.

Model/ensemble weights and decision bias are fitted using outer-training labels
only. Outer test labels are used solely for the recorded final arm scores.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import time
import warnings

import joblib
import numpy as np
from joblib import Parallel, delayed, parallel_backend
from scipy.optimize import minimize
from sklearn.base import clone
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import SelectPercentile, VarianceThreshold, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits

from ml.artifacts import artifact_run, resolve_artifact, write_json
from ml.config import DATA_DIR, validate_cv
from ml.records import load_raw_participants, validate_sessions
from ml.utils.advanced_features import AdvancedFeatureView, advanced_features
from ml.utils.features import target_label


@dataclass
class Candidate:
    name: str
    estimator: object
    use_auxiliary: bool = False


def candidate_pool(seed=42, include_tabpfn=True):
    try:
        from catboost import CatBoostClassifier
        from lightgbm import LGBMClassifier
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError(
            "Install requirements-research.txt to run the advanced benchmark."
        ) from exc
    pool = []

    def add(
        name, model, views=("summary", "rich"), percentiles=(100,), auxiliary=False, extra=None
    ):
        for view in views:
            for percentile in percentiles:
                steps = [
                    ("view", AdvancedFeatureView(view)),
                    ("vectorize", DictVectorizer(sparse=False)),
                    ("variance", VarianceThreshold()),
                    ("scale", StandardScaler()),
                    ("select", SelectPercentile(f_classif, percentile=percentile)),
                ]
                if extra is not None:
                    steps.append(("reduce", clone(extra)))
                steps.append(("model", clone(model)))
                pool.append(
                    Candidate(
                        f"{name}-{view}-p{percentile}" + ("-aux" if auxiliary else ""),
                        Pipeline(steps),
                        auxiliary,
                    )
                )

    add("majority", DummyClassifier(strategy="prior"), views=("summary",))
    for c in (0.0001, 0.001, 0.01, 0.1, 1.0):
        for balanced in (False, True):
            add(
                f"logit-c{c}-b{int(balanced)}",
                LogisticRegression(
                    C=c,
                    class_weight="balanced" if balanced else None,
                    max_iter=3000,
                    random_state=seed,
                ),
                views=("summary", "rich", "sequence", "combined"),
            )
    for c in (0.001, 0.01, 0.1):
        add(
            f"logit-aux-c{c}",
            LogisticRegression(C=c, max_iter=3000, random_state=seed),
            views=("summary", "rich"),
            auxiliary=True,
        )
    for c in (0.01, 0.1, 1.0):
        add(
            f"sparse-c{c}",
            LogisticRegression(C=c, solver="saga", l1_ratio=0.75, max_iter=5000, random_state=seed),
            views=("rich", "combined"),
            percentiles=(25, 100),
        )
    for shrinkage in ("auto", 0.5, 0.9):
        add(f"lda-{shrinkage}", LinearDiscriminantAnalysis(solver="lsqr", shrinkage=shrinkage))
    for c in (0.1, 1.0, 10.0):
        for gamma in ("scale", 0.001):
            add(
                f"svm-c{c}-g{gamma}",
                SVC(C=c, gamma=gamma, probability=True, random_state=seed),
                views=("summary", "rich", "sequence"),
            )
    for c in (0.01, 0.1):
        add(
            f"selected-logit-c{c}",
            LogisticRegression(C=c, max_iter=3000, random_state=seed),
            views=("rich", "combined"),
            percentiles=(10, 25, 50),
        )
        add(
            f"pca-logit-c{c}",
            LogisticRegression(C=c, max_iter=3000, random_state=seed),
            views=("rich", "sequence"),
            extra=PCA(n_components=0.9, svd_solver="full"),
        )
    add(
        "interaction-logit",
        LogisticRegression(C=0.01, max_iter=3000, random_state=seed),
        views=("rich",),
        percentiles=(5,),
        extra=PolynomialFeatures(degree=2, interaction_only=True, include_bias=False),
    )
    for neighbors in (5, 11, 21):
        add(
            f"neighbors-{neighbors}",
            KNeighborsClassifier(n_neighbors=neighbors, weights="distance", metric="cosine"),
            views=("summary", "rich"),
        )
    for depth in (2, 4, 6):
        for regularization in (3.0, 30.0):
            model = CatBoostClassifier(
                iterations=300,
                depth=depth,
                l2_leaf_reg=regularization,
                learning_rate=0.03,
                verbose=False,
                allow_writing_files=False,
                thread_count=1,
                random_seed=seed,
            )
            add(
                f"catboost-d{depth}-l{regularization}", model, views=("summary", "rich", "sequence")
            )
            if depth == 4:
                add(f"catboost-aux-l{regularization}", model, views=("rich",), auxiliary=True)
    for depth in (1, 3):
        for child in (3, 10):
            for regularization in (1.0, 10.0):
                add(
                    f"xgb-d{depth}-child{child}-l{regularization}",
                    XGBClassifier(
                        n_estimators=300,
                        max_depth=depth,
                        min_child_weight=child,
                        reg_lambda=regularization,
                        learning_rate=0.03,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        tree_method="hist",
                        n_jobs=1,
                        random_state=seed,
                    ),
                    views=("summary", "rich"),
                )
    for leaves in (3, 7):
        for child in (10, 25):
            add(
                f"lgb-leaves{leaves}-child{child}",
                LGBMClassifier(
                    n_estimators=250,
                    num_leaves=leaves,
                    min_child_samples=child,
                    reg_lambda=10.0,
                    learning_rate=0.03,
                    verbosity=-1,
                    n_jobs=1,
                    random_state=seed,
                ),
                views=("summary", "rich"),
            )
    for model_class in (RandomForestClassifier, ExtraTreesClassifier):
        for leaf in (3, 10):
            add(
                f"{model_class.__name__}-leaf{leaf}",
                model_class(
                    n_estimators=300,
                    min_samples_leaf=leaf,
                    max_features=0.5,
                    n_jobs=1,
                    random_state=seed,
                ),
                views=("summary", "rich"),
            )
    if include_tabpfn:
        os.environ["TABPFN_DISABLE_TELEMETRY"] = "1"
        os.environ["TABPFN_NO_BROWSER"] = "1"
        from tabpfn import TabPFNClassifier
        from tabpfn.constants import ModelVersion

        model = TabPFNClassifier.create_default_for_version(
            ModelVersion.V2,
            device="cpu",
            n_estimators=4,
            auto_scale_n_estimators=False,
            random_state=seed,
            n_preprocessing_jobs=1,
        )
        add("tabpfn-v2", model, views=("summary", "rich"), percentiles=(25,))
    return pool


def _probability(model, features):
    return np.clip(np.asarray(model.predict_proba(features))[:, 1], 1e-6, 1 - 1e-6)


def _fit(candidate, features, labels, aux_features, aux_labels):
    if candidate.use_auxiliary and len(aux_features):
        features = list(features) + list(aux_features)
        labels = np.r_[labels, aux_labels]
    return clone(candidate.estimator).fit(features, labels)


def fit_ensemble(probabilities, labels, maximum_members=30):
    """Nonnegative simplex weights, fitted on training OOF predictions only."""
    losses = np.array([log_loss(labels, p, labels=[0, 1]) for p in probabilities.T])
    selected = np.argsort(losses, kind="stable")[: min(maximum_members, len(losses))]
    p = probabilities[:, selected]
    initial = np.full(len(selected), 1 / len(selected))

    def objective(weights):
        prediction = np.clip(p @ weights, 1e-6, 1 - 1e-6)
        value = float(
            -np.mean(labels * np.log(prediction) + (1 - labels) * np.log(1 - prediction))
        ) + 0.05 * np.sum((weights - initial) ** 2)
        gradient = p.T @ ((prediction - labels) / (prediction * (1 - prediction))) / len(
            labels
        ) + 0.1 * (weights - initial)
        return value, gradient

    result = minimize(
        objective,
        initial,
        jac=True,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * len(selected),
        constraints={
            "type": "eq",
            "fun": lambda w: float(w.sum() - 1),
            "jac": lambda w: np.ones(len(w)),
        },
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not result.success:
        raise RuntimeError(f"Ensemble weight fitting failed: {result.message}")
    weights = np.zeros(probabilities.shape[1])
    weights[selected] = result.x
    weights[weights < 1e-6] = 0
    weights /= weights.sum()
    prediction = probabilities @ weights
    thresholds = np.linspace(0.3, 0.7, 17)
    # Deterministic tie break favors the usual .5 threshold.
    threshold = max(
        thresholds, key=lambda t: (accuracy_score(labels, prediction >= t), -abs(t - 0.5))
    )
    return weights, float(threshold)


def _inner_predictions(index, candidate, features, labels, aux_features, aux_labels, splits, cache):
    path = cache / f"{candidate.name}.json"
    if path.exists():
        saved = json.loads(path.read_text())
        probabilities = np.asarray(saved["probabilities"], dtype=float)
        if probabilities.shape == (len(labels),) and np.isfinite(probabilities).all():
            return index, probabilities, None
    try:
        total = np.zeros(len(labels))
        counts = np.zeros(len(labels))
        for train, test in splits:
            model = _fit(
                candidate, [features[i] for i in train], labels[train], aux_features, aux_labels
            )
            total[test] += _probability(model, [features[i] for i in test])
            counts[test] += 1
        if np.any(counts == 0):
            raise RuntimeError("Incomplete inner out-of-fold predictions.")
        probabilities = total / counts
        write_json(path, {"probabilities": probabilities.tolist()})
        return index, probabilities, None
    except Exception as exc:
        return index, None, f"{type(exc).__name__}: {exc}"


def _search(
    pool, features, labels, aux_features, aux_labels, seed, inner_folds, repeats, jobs, cache
):
    splits = list(
        RepeatedStratifiedKFold(n_splits=inner_folds, n_repeats=repeats, random_state=seed).split(
            np.zeros(len(labels)), labels
        )
    )
    predictions = {}
    errors = {}
    for done, (index, probability, error) in enumerate(
        Parallel(n_jobs=jobs, return_as="generator_unordered")(
            delayed(_inner_predictions)(
                i, c, features, labels, aux_features, aux_labels, splits, cache
            )
            for i, c in enumerate(pool)
        ),
        1,
    ):
        if error is None:
            predictions[index] = probability
        else:
            errors[pool[index].name] = error
        if done % 20 == 0 or done == len(pool):
            print(
                f"[benchmark] inner candidates {done}/{len(pool)}; failed={len(errors)}", flush=True
            )
    if len(predictions) < max(1, len(pool) // 2):
        raise RuntimeError(f"Too many candidate failures: {errors}")
    indices = sorted(predictions)
    matrix = np.column_stack([predictions[i] for i in indices])
    weights, threshold = fit_ensemble(matrix, labels)
    single = max(
        range(len(indices)),
        key=lambda i: (
            accuracy_score(labels, matrix[:, i] >= 0.5),
            -log_loss(labels, matrix[:, i], labels=[0, 1]),
        ),
    )
    top = sorted(
        range(len(indices)),
        key=lambda i: (
            -accuracy_score(labels, matrix[:, i] >= 0.5),
            log_loss(labels, matrix[:, i], labels=[0, 1]),
        ),
    )[:5]
    return indices, matrix, weights, threshold, single, top, errors


@dataclass
class AdvancedPredictor:
    models: list
    weights: np.ndarray
    threshold: float

    def predict_proba(self, sessions):
        features = [advanced_features(s) for s in sessions]
        probabilities = (
            np.column_stack([_probability(model, features) for model in self.models]) @ self.weights
        )
        return np.column_stack([1 - probabilities, probabilities])

    def predict(self, sessions):
        return (self.predict_proba(sessions)[:, 1] >= self.threshold).astype(int)


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _versions():
    versions = {}
    for name in ("numpy", "scikit-learn", "catboost", "xgboost", "lightgbm", "tabpfn", "torch"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def run_advanced_benchmark(
    *,
    sessions=None,
    auxiliary_sessions=None,
    output_dir=None,
    seed=42,
    outer_folds=5,
    inner_folds=3,
    repeats=2,
    jobs=4,
    include_tabpfn=True,
    pool=None,
):
    sessions = list(sessions) if sessions is not None else load_raw_participants()
    validate_sessions(sessions)
    if any(sum(t["task_id"] == "risk_pref" for t in s["trials"]) != 30 for s in sessions):
        raise ValueError(
            "The benchmark requires all 30 risk trials for every evaluation participant."
        )
    identities = {s["participant_id"] for s in sessions}
    auxiliary_sessions = list(auxiliary_sessions or [])
    if auxiliary_sessions:
        validate_sessions(auxiliary_sessions)
    auxiliary = [s for s in auxiliary_sessions if s["participant_id"] not in identities]
    if any(sum(t["task_id"] == "risk_pref" for t in s["trials"]) != 30 for s in auxiliary):
        raise ValueError("Auxiliary participants must have all 30 risk trials.")
    if repeats < 1:
        raise ValueError("Inner repeats must be positive.")
    labels = np.array([target_label(s, "risk_pref") for s in sessions])
    aux_labels = np.array([target_label(s, "risk_pref") for s in auxiliary], dtype=int)
    validate_cv(labels, outer_folds, inner_folds, jobs)
    pool = pool if pool is not None else candidate_pool(seed, include_tabpfn)
    if not auxiliary:
        pool = [candidate for candidate in pool if not candidate.use_auxiliary]
    features = [advanced_features(s) for s in sessions]
    aux_features = [advanced_features(s) for s in auxiliary]
    root = Path(output_dir) if output_dir else DATA_DIR / "optimization_advanced_risk_pref"
    source_hash = hashlib.sha256(
        b"".join(
            Path(__file__).with_name(name).read_bytes()
            for name in (
                "advanced_benchmark.py",
                "advanced_features.py",
                "features.py",
                "behavioral_models.py",
            )
        )
    ).hexdigest()
    key = _fingerprint(
        {
            "data": _fingerprint(sessions),
            "auxiliary": _fingerprint(auxiliary),
            "source": source_hash,
            "seed": seed,
            "inner_folds": inner_folds,
            "repeats": repeats,
            "outer_folds": outer_folds,
            "candidates": [(c.name, c.use_auxiliary) for c in pool],
            "versions": _versions(),
        }
    )
    work = root / "work" / key[:16]
    arms = {
        name: np.zeros(len(labels), dtype=int)
        for name in ("weighted_ensemble", "best_single", "top5_average", "majority")
    }
    scores = {name: np.zeros(len(labels)) for name in arms}
    fold_ids = np.zeros(len(labels), dtype=int)
    folds = []
    started = time.monotonic()
    print(
        f"[benchmark] n={len(labels)} auxiliary={len(auxiliary)} candidates={len(pool)} target=85% ({math.ceil(0.85 * len(labels))} correct)",
        flush=True,
    )
    # Prevent oversubscription of small matrix operations inside parallel fits.
    warnings.filterwarnings(
        "ignore", message="X does not have valid feature names.*", category=UserWarning
    )
    with threadpool_limits(limits=1), parallel_backend("loky", inner_max_num_threads=1):
        for fold, (train, test) in enumerate(
            StratifiedKFold(outer_folds, shuffle=True, random_state=seed).split(
                np.zeros(len(labels)), labels
            ),
            1,
        ):
            print(f"[benchmark] outer fold {fold}/{outer_folds}", flush=True)
            training = [features[i] for i in train]
            testing = [features[i] for i in test]
            indices, matrix, weights, threshold, single, top, errors = _search(
                pool,
                training,
                labels[train],
                aux_features,
                aux_labels,
                seed,
                inner_folds,
                repeats,
                jobs,
                work / f"fold{fold}",
            )
            required = sorted(set(np.flatnonzero(weights).tolist() + [single] + top))
            test_prob = {}
            for local in required:
                model = _fit(
                    pool[indices[local]], training, labels[train], aux_features, aux_labels
                )
                test_prob[local] = _probability(model, testing)
            ensemble = sum(weights[i] * test_prob[i] for i in required if weights[i] > 0)
            scores["weighted_ensemble"][test] = ensemble
            arms["weighted_ensemble"][test] = (ensemble >= threshold).astype(int)
            scores["best_single"][test] = test_prob[single]
            arms["best_single"][test] = (test_prob[single] >= 0.5).astype(int)
            average = np.mean([test_prob[i] for i in top], axis=0)
            scores["top5_average"][test] = average
            arms["top5_average"][test] = (average >= 0.5).astype(int)
            prevalence = float(labels[train].mean())
            scores["majority"][test] = prevalence
            arms["majority"][test] = int(prevalence >= 0.5)
            fold_ids[test] = fold
            fold_result = {
                "fold": fold,
                "n_train": len(train),
                "n_test": len(test),
                "threshold": threshold,
                "weights": {
                    pool[indices[i]].name: float(w) for i, w in enumerate(weights) if w > 0
                },
                "selected_single": pool[indices[single]].name,
                "errors": errors,
                "test_accuracy": {
                    name: float(accuracy_score(labels[test], prediction[test]))
                    for name, prediction in arms.items()
                },
            }
            folds.append(fold_result)
            write_json(work / f"fold{fold}_complete.json", fold_result)
            print(f"[benchmark] fold={fold} accuracy={fold_result['test_accuracy']}", flush=True)
        print("[benchmark] fitting final deployment ensemble", flush=True)
        indices, matrix, weights, threshold, single, top, errors = _search(
            pool,
            features,
            labels,
            aux_features,
            aux_labels,
            seed,
            inner_folds,
            repeats,
            jobs,
            work / "deployment",
        )
        selected = np.flatnonzero(weights)
        final_models = [
            _fit(pool[indices[i]], features, labels, aux_features, aux_labels) for i in selected
        ]
    if np.any(fold_ids == 0):
        raise RuntimeError("Incomplete benchmark fold coverage.")
    metrics = {
        name: {
            "accuracy": float(accuracy_score(labels, prediction)),
            "balanced_accuracy": float(balanced_accuracy_score(labels, prediction)),
            "auc": float(roc_auc_score(labels, scores[name])),
            "correct": int((labels == prediction).sum()),
            "n": len(labels),
        }
        for name, prediction in arms.items()
    }
    result = {
        "primary_arm": "weighted_ensemble",
        "target_accuracy": 0.85,
        "target_met": metrics["weighted_ensemble"]["accuracy"] >= 0.85,
        "target_definition": "Gamble on at least half of the same 30 risk trials; unchanged.",
        "protocol": "Nested participant CV; repeated inner OOF model selection; training-only ensemble weights and threshold.",
        "n_participants": len(labels),
        "n_auxiliary_training_only": len(auxiliary),
        "candidate_count": len(pool),
        "seed": seed,
        "outer_folds": outer_folds,
        "inner_folds": inner_folds,
        "inner_repeats": repeats,
        "metrics": metrics,
        "folds": folds,
        "deployment_weights": {pool[indices[i]].name: float(weights[i]) for i in selected},
        "deployment_threshold": threshold,
        "data_sha256": _fingerprint(sessions),
        "auxiliary_sha256": _fingerprint(auxiliary),
        "source_sha256": source_hash,
        "duration_seconds": time.monotonic() - started,
        "deployment_errors": errors,
        "limitations": [
            "Exploratory reuse of a previously inspected cohort; new-cohort confirmation is required.",
            "All prespecified arm scores are retained; an individual high-scoring fold is not the result.",
            "Participant provenance is unspecified; these numbers alone do not establish a human behavioral finding.",
        ],
        "versions": _versions(),
    }
    rows = [
        {
            "participant_hash": hashlib.sha256(s["participant_id"].encode()).hexdigest(),
            "fold": int(fold_ids[i]),
            "observed": int(labels[i]),
            "predictions": {name: int(prediction[i]) for name, prediction in arms.items()},
        }
        for i, s in enumerate(sessions)
    ]
    with artifact_run(root) as published:
        write_json(published / "results.json", result)
        write_json(published / "predictions.json", rows)
        write_json(
            published / "weights_and_biases.json",
            {
                "weights": result["deployment_weights"],
                "threshold": threshold,
                "log_odds_bias": float(-np.log(threshold / (1 - threshold))),
            },
        )
        joblib.dump(
            AdvancedPredictor(final_models, weights[selected], threshold),
            published / "predictor.joblib",
        )
    print(f"[benchmark] FINAL {metrics}; target_met={result['target_met']}", flush=True)
    return result


def predict_advanced(path, sessions):
    return joblib.load(resolve_artifact(Path(path))).predict(sessions)
