"""Explicit developmental-context control; separate from behavior-only prediction."""

from pathlib import Path
import hashlib
import json

import joblib
import numpy as np
from joblib import parallel_backend
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from ml.artifacts import artifact_run, resolve_artifact, write_json
from ml.config import DATA_DIR, validate_cv
from ml.records import load_raw_participants, validate_sessions
from ml.utils.features import behavior_features, target_label


class CovariateFeatures(TransformerMixin, BaseEstimator):
    def __init__(self, view="combined"):
        self.view = view

    def fit(self, X, y=None):
        if self.view not in ("behavior", "demographics", "combined"):
            raise ValueError("Invalid covariate view.")
        return self

    def transform(self, X):
        rows = []
        for session in X:
            if "trials" not in session:
                rows.append(
                    {
                        k: v
                        for k, v in session.items()
                        if self.view == "combined"
                        or (k.startswith("context.") == (self.view == "demographics"))
                    }
                )
                continue
            row = (
                behavior_features(session, "risk_pref", include_mechanisms=False)
                if self.view != "demographics"
                else {}
            )
            if self.view != "behavior":
                age, school = session.get("age"), session.get("school_class")
                if not isinstance(age, (int, float)) or not isinstance(school, (int, float)):
                    raise ValueError("Covariate prediction requires recorded age and school_class.")
                row.update(
                    {
                        "context.age": float(age),
                        "context.school_class": float(school),
                        "context.age_group": str(age),
                        "context.school_group": str(school),
                    }
                )
            rows.append(row)
        return rows


def _search(view, seed, inner_folds, jobs):
    pipeline = Pipeline(
        [
            ("features", CovariateFeatures(view)),
            ("vector", DictVectorizer(sparse=False)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=3000)),
        ]
    )
    grid = [
        {
            "model": [LogisticRegression(max_iter=3000, random_state=seed)],
            "model__C": [0.001, 0.01, 0.1, 1.0, 10.0],
            "model__class_weight": [None, "balanced"],
        },
        {
            "model": [RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=1)],
            "model__max_depth": [3, None],
            "model__min_samples_leaf": [3, 8],
        },
        {
            "model": [
                HistGradientBoostingClassifier(
                    max_iter=200, max_leaf_nodes=3, min_samples_leaf=10, random_state=seed
                )
            ],
            "model__l2_regularization": [1.0, 10.0],
        },
    ]
    return GridSearchCV(
        pipeline,
        grid,
        scoring="accuracy",
        cv=StratifiedKFold(inner_folds, shuffle=True, random_state=seed),
        n_jobs=jobs,
        error_score="raise",
    )


def run_covariate_benchmark(
    *, sessions=None, seed=42, outer_folds=5, inner_folds=3, jobs=2, output_dir=None
):
    sessions = list(sessions) if sessions is not None else load_raw_participants()
    validate_sessions(sessions)
    if any(sum(t["task_id"] == "risk_pref" for t in s["trials"]) != 30 for s in sessions):
        raise ValueError("The covariate benchmark requires all 30 risk trials.")
    labels = np.array([target_label(s, "risk_pref") for s in sessions])
    prepared = CovariateFeatures("combined").fit_transform(sessions)
    validate_cv(labels, outer_folds, inner_folds, jobs)
    predictions = {
        view: np.zeros(len(labels), dtype=int) for view in ("demographics", "behavior", "combined")
    }
    scores = {view: np.zeros(len(labels)) for view in predictions}
    fold_ids = np.zeros(len(labels), dtype=int)
    folds = []
    with threadpool_limits(limits=1), parallel_backend("loky", inner_max_num_threads=1):
        for fold, (train, test) in enumerate(
            StratifiedKFold(outer_folds, shuffle=True, random_state=seed).split(
                np.zeros(len(labels)), labels
            ),
            1,
        ):
            row = {"fold": fold, "models": {}}
            for view in predictions:
                search = _search(view, seed, inner_folds, jobs).fit(
                    [prepared[i] for i in train], labels[train]
                )
                predictions[view][test] = search.predict([prepared[i] for i in test])
                scores[view][test] = search.predict_proba([prepared[i] for i in test])[:, 1]
                row["models"][view] = {
                    "parameters": {
                        k: type(v).__name__ if k == "model" else v
                        for k, v in search.best_params_.items()
                    },
                    "accuracy": float(accuracy_score(labels[test], predictions[view][test])),
                }
            fold_ids[test] = fold
            folds.append(row)
            print(
                f"[covariate] fold={fold} accuracy="
                + str({k: v["accuracy"] for k, v in row["models"].items()}),
                flush=True,
            )
        final = {
            view: _search(view, seed, inner_folds, jobs).fit(prepared, labels).best_estimator_
            for view in predictions
        }
    metrics = {
        view: {
            "accuracy": float(accuracy_score(labels, p)),
            "balanced_accuracy": float(balanced_accuracy_score(labels, p)),
            "auc": float(roc_auc_score(labels, scores[view])),
            "correct": int((p == labels).sum()),
            "n": len(labels),
        }
        for view, p in predictions.items()
    }
    result = {
        "primary_arm": "combined",
        "target_accuracy": 0.85,
        "target_met": metrics["combined"]["accuracy"] >= 0.85,
        "protocol": "Nested participant CV with the same risk label; age/class are explicitly available input covariates in the combined arm.",
        "metrics": metrics,
        "folds": folds,
        "seed": seed,
        "outer_folds": outer_folds,
        "inner_folds": inner_folds,
        "n_participants": len(labels),
        "candidate_count_per_view": 16,
        "data_sha256": hashlib.sha256(
            json.dumps(sessions, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "limitations": [
            "Different input scope from behavior-only models; compare against the demographic-only control.",
            "Exploratory reuse of an inspected cohort; confirmation requires new participants.",
        ],
    }
    root = Path(output_dir) if output_dir else DATA_DIR / "optimization_covariate_risk"
    rows = [
        {
            "participant_hash": hashlib.sha256(s["participant_id"].encode()).hexdigest(),
            "fold": int(fold_ids[i]),
            "observed": int(labels[i]),
            "predictions": {view: int(p[i]) for view, p in predictions.items()},
        }
        for i, s in enumerate(sessions)
    ]
    with artifact_run(root) as published:
        write_json(published / "results.json", result)
        write_json(published / "predictions.json", rows)
        joblib.dump(final, published / "predictors.joblib")
    print(f"[covariate] FINAL {metrics}; target_met={result['target_met']}", flush=True)
    return result


def predict_covariates(path, sessions, view="combined"):
    if view not in ("combined", "behavior", "demographics"):
        raise ValueError("Invalid covariate view.")
    return joblib.load(resolve_artifact(Path(path)))[view].predict(sessions)
