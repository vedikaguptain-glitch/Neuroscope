"""Nested participant-level model selection for cross-task behavioral prediction.

Feature extraction is participant-local and removes the target task before reading
any trial fields. Vocabulary fitting, scaling and model selection happen inside
the training folds. The final all-data fit is for deployment, not evaluation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
from ml.artifacts import artifact_run, resolve_artifact
import numpy as np
import sklearn
from joblib import parallel_backend
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
    StackingClassifier,
)
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    roc_auc_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    ParameterGrid,
    StratifiedKFold,
    TunedThresholdClassifierCV,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits

from ml.config import PROJECT_ROOT, TASK_ORDER, validate_cv
from ml.records import load_raw_participants, validate_sessions
from ml.utils.behavioral_models import FeatureView

from ml.utils.features import TARGET_ACTIONS, behavior_features, target_label

FEATURE_VERSION = 2


def _linear_pipeline(
    seed: int, mode: str = "summary", task: str | None = None, c: float = 0.01
) -> Pipeline:
    return Pipeline(
        [
            ("view", FeatureView(mode=mode, task=task)),
            ("vectorize", DictVectorizer(sparse=False)),
            ("variance", "passthrough" if task else VarianceThreshold()),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=c, max_iter=3000, random_state=seed)),
        ]
    )


def candidate_search(
    seed: int,
    inner_folds: int = 3,
    jobs: int = 4,
    held_out_task: str = "risk_pref",
    profile: str = "summary",
) -> GridSearchCV:
    if profile not in ("summary", "behavioral"):
        raise ValueError("Unknown model search profile.")
    pipeline = _linear_pipeline(seed)
    grid = [
        {"model": [DummyClassifier(strategy="most_frequent")]},
        {
            "model": [LogisticRegression(max_iter=3000, random_state=seed)],
            "model__C": [0.001, 0.01, 0.1, 1, 10],
            "model__class_weight": [None, "balanced"],
        },
        {
            "model": [SVC(kernel="rbf", random_state=seed)],
            "model__C": [0.1, 1, 10],
            "model__gamma": ["scale", 0.001, 0.01],
            "model__class_weight": [None, "balanced"],
        },
        {
            "model": [LinearDiscriminantAnalysis(solver="lsqr")],
            "model__shrinkage": ["auto", 0.5, 0.9],
        },
        {
            "model": [
                RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=1),
                ExtraTreesClassifier(n_estimators=200, random_state=seed, n_jobs=1),
            ],
            "model__min_samples_leaf": [3, 8],
            "model__max_depth": [3, None],
        },
    ]
    # Preserve the original search as an explicit feature view, then add a fixed
    # extension. No outer test labels are used to choose feature families or bias.
    for group in grid:
        group["view__mode"] = ["summary"]
    summary_groups = len(grid)
    grid.extend(
        [
            {
                "view__mode": ["mechanism", "all"],
                "model": [LogisticRegression(max_iter=3000, random_state=seed)],
                "model__C": [0.001, 0.01, 0.1, 1, 10],
                "model__class_weight": [None, "balanced"],
            },
            {
                "view__mode": ["mechanism", "all"],
                "model": [SVC(kernel="rbf", random_state=seed)],
                "model__C": [0.1, 1, 10],
                "model__class_weight": [None, "balanced"],
            },
            {
                "view__mode": ["all"],
                "model": [
                    HistGradientBoostingClassifier(
                        max_iter=150, learning_rate=0.05, random_state=seed
                    )
                ],
                "model__max_leaf_nodes": [3, 7],
                "model__l2_regularization": [1.0, 10.0],
            },
        ]
    )
    # These estimators receive raw dictionaries so their own CV refits the entire
    # feature/scaling pipeline. Pre-scaling would contaminate their internal folds.
    passthrough = {
        "view": ["passthrough"],
        "vectorize": ["passthrough"],
        "variance": ["passthrough"],
        "scale": ["passthrough"],
    }
    tuned = TunedThresholdClassifierCV(
        _linear_pipeline(seed, mode="all"),
        scoring="accuracy",
        thresholds=np.linspace(0.25, 0.75, 21),
        cv=StratifiedKFold(3, shuffle=True, random_state=seed),
        n_jobs=1,
        store_cv_results=True,
    )
    grid.append(
        {
            **passthrough,
            "model": [tuned],
            "model__estimator__view__mode": ["mechanism", "all"],
            "model__estimator__model__C": [0.001, 0.01, 0.1],
            "model__estimator__model__class_weight": [None, "balanced"],
        }
    )
    # A ridge logistic meta-model learns task weights AND an intercept from
    # out-of-fold training predictions, rather than in-sample fitted predictions.
    bases = [
        (task, _linear_pipeline(seed, mode="all", task=task, c=0.1))
        for task in TASK_ORDER
        if task != held_out_task
    ]
    bases.extend(
        [
            ("summary", _linear_pipeline(seed)),
            ("mechanism", _linear_pipeline(seed, mode="mechanism", c=0.1)),
        ]
    )
    stack = StackingClassifier(
        bases,
        final_estimator=LogisticRegression(max_iter=3000, random_state=seed),
        cv=StratifiedKFold(3, shuffle=True, random_state=seed),
        stack_method="predict_proba",
        n_jobs=1,
    )
    grid.append(
        {
            **passthrough,
            "model": [stack],
            "model__final_estimator__C": [0.1, 1, 10],
            "model__final_estimator__class_weight": [None, "balanced"],
        }
    )
    if profile == "summary":
        grid = grid[:summary_groups]
    return GridSearchCV(
        pipeline,
        grid,
        scoring={"accuracy": "accuracy", "balanced_accuracy": "balanced_accuracy"},
        refit="accuracy",
        cv=StratifiedKFold(inner_folds, shuffle=True, random_state=seed),
        n_jobs=jobs,
        error_score="raise",
        return_train_score=False,
    )


def _description(params: dict[str, Any]) -> dict[str, Any]:
    return {k: type(v).__name__ if k == "model" else v for k, v in params.items()}


def model_parameters(estimator, feature_names=None) -> dict[str, Any]:
    """Export fitted prediction weights with their feature units and intercepts."""
    if isinstance(estimator, Pipeline):
        vectorizer = estimator.named_steps.get("vectorize")
        if isinstance(vectorizer, DictVectorizer):
            feature_names = vectorizer.get_feature_names_out()
            variance = estimator.named_steps.get("variance")
            if isinstance(variance, VarianceThreshold):
                feature_names = feature_names[variance.get_support()]
        fitted = estimator.named_steps.get("model", estimator.steps[-1][1])
        return model_parameters(fitted, feature_names)
    result: dict[str, Any] = {"model": type(estimator).__name__}
    if isinstance(estimator, TunedThresholdClassifierCV):
        threshold = float(estimator.best_threshold_)
        result.update(
            threshold=threshold,
            additional_log_odds_bias=float(-np.log(threshold / (1 - threshold))),
            classifier=model_parameters(estimator.estimator_),
        )
    elif isinstance(estimator, StackingClassifier):
        names = [name for name, _ in estimator.estimators]
        result["task_and_view_weights"] = model_parameters(estimator.final_estimator_, names)
        result["base_models"] = {
            name: model_parameters(model) for name, model in zip(names, estimator.estimators_)
        }
    elif hasattr(estimator, "coef_"):
        names = (
            list(feature_names)
            if feature_names is not None
            else [str(i) for i in range(estimator.coef_.shape[-1])]
        )
        result["intercept"] = np.asarray(estimator.intercept_).tolist()
        result["weights"] = sorted(
            [
                {"feature": str(name), "weight": float(weight)}
                for name, weight in zip(names, estimator.coef_[0])
            ],
            key=lambda row: abs(row["weight"]),
            reverse=True,
        )
        result["interpretation"] = (
            "Conditional prediction associations; base feature coefficients use training-standardized inputs. Meta weights use base probabilities. Not causal effects or validated trait measurements."
        )
    elif hasattr(estimator, "feature_importances_"):
        result["feature_importances"] = [
            {"feature": str(name), "importance": float(weight)}
            for name, weight in zip(feature_names, estimator.feature_importances_)
        ]
    return result


def run_optimization(
    *,
    held_out_task: str = "risk_pref",
    seed: int = 42,
    outer_folds: int = 5,
    inner_folds: int = 3,
    jobs: int = 4,
    profile: str = "summary",
    sessions: Sequence[Mapping[str, Any]] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    sessions = list(sessions) if sessions is not None else load_raw_participants()
    ids = [str(s.get("participant_id", "")) for s in sessions]
    if not sessions or any(not v for v in ids) or len(set(ids)) != len(ids):
        raise RuntimeError("Optimization requires distinct, nonempty participant IDs.")
    validate_sessions(sessions)
    if outer_folds < 2 or inner_folds < 2:
        raise RuntimeError("Both outer and inner cross-validation require at least two folds.")
    if jobs < 1:
        raise RuntimeError("jobs must be positive.")
    labels = np.array([target_label(s, held_out_task) for s in sessions])
    classes, counts = np.unique(labels, return_counts=True)
    if len(classes) != 2 or int(counts.min()) < outer_folds:
        raise RuntimeError("Not enough participants in both classes for the requested outer folds.")
    validate_cv(labels, outer_folds, inner_folds, jobs)
    features = [behavior_features(s, held_out_task) for s in sessions]
    predictions = np.full(len(labels), -1, dtype=int)
    baseline = np.full(len(labels), -1, dtype=int)
    scores = np.full(len(labels), np.nan)
    fold_ids = np.full(len(labels), -1, dtype=int)
    fold_results = []
    fold_parameters = []
    outer = StratifiedKFold(outer_folds, shuffle=True, random_state=seed)
    print(
        f"[optimize] target={held_out_task} participants={len(labels)} outer={outer_folds} inner={inner_folds}",
        flush=True,
    )
    with threadpool_limits(limits=1), parallel_backend("threading"):
        for fold, (train, test) in enumerate(outer.split(np.zeros(len(labels)), labels), 1):
            if np.bincount(labels[train], minlength=2).min() < inner_folds:
                raise RuntimeError("Not enough training participants per class for inner folds.")
            search = candidate_search(
                seed, inner_folds, jobs, held_out_task=held_out_task, profile=profile
            )
            search.fit([features[i] for i in train], labels[train])
            model = search.best_estimator_
            test_features = [features[i] for i in test]
            predictions[test] = model.predict(test_features)
            if hasattr(model, "predict_proba"):
                scores[test] = model.predict_proba(test_features)[:, 1]
            else:
                scores[test] = model.decision_function(test_features)
            baseline[test] = np.bincount(labels[train], minlength=2).argmax()
            fold_ids[test] = fold
            params = _description(search.best_params_)
            result = {
                "fold": fold,
                "n_train": len(train),
                "n_test": len(test),
                "inner_accuracy": float(search.best_score_),
                "selected": params,
                "test_accuracy": float(accuracy_score(labels[test], predictions[test])),
                "baseline_accuracy": float(accuracy_score(labels[test], baseline[test])),
            }
            fold_results.append(result)
            fold_parameters.append({"fold": fold, "parameters": model_parameters(model)})
            print(
                f"[optimize] fold={fold} selected={params} test={result['test_accuracy']:.3f} baseline={result['baseline_accuracy']:.3f}",
                flush=True,
            )
        # Deployment model: choose with inner CV, then refit all available data.
        final_search = candidate_search(
            seed, inner_folds, jobs, held_out_task=held_out_task, profile=profile
        )
        final_search.fit(features, labels)
    if (predictions < 0).any() or not np.isfinite(scores).all():
        raise RuntimeError("Incomplete out-of-fold predictions.")
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "held_out_task": held_out_task,
        "target_definition": f"{TARGET_ACTIONS[held_out_task]} on at least half of valid target responses",
        "protocol": "nested stratified participant cross-validation; family and hyperparameters selected inside each outer training fold",
        "primary_metric": "accuracy",
        "seed": seed,
        "outer_folds": outer_folds,
        "inner_folds": inner_folds,
        "candidate_configurations": len(ParameterGrid(final_search.param_grid)),
        "feature_version": FEATURE_VERSION,
        "n_participants": len(labels),
        "search_profile": profile,
        "data_sha256": hashlib.sha256(
            json.dumps(sessions, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "class_counts": {str(c): int(n) for c, n in zip(classes, counts)},
        "accuracy": float(accuracy_score(labels, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
        # AUC is computed inside folds because score units can differ across families.
        "mean_fold_auc": float(
            np.mean(
                [
                    roc_auc_score(labels[fold_ids == f], scores[fold_ids == f])
                    for f in range(1, outer_folds + 1)
                ]
            )
        ),
        "majority_baseline": float(accuracy_score(labels, baseline)),
        "folds": fold_results,
        "deployment_selected": _description(final_search.best_params_),
        "deployment_selection_cv_accuracy": float(final_search.best_score_),
        "report": classification_report(labels, predictions, output_dict=True, zero_division=0),
        "limitations": [
            "Exploratory internal cross-validation, not confirmation on a new cohort.",
            "Feature development follows earlier inspection of this sample; repeated development can overfit the evaluation protocol.",
            "The original binary target definition is preserved; this is not a clinical or trait validation.",
            "Deployment selection score is not an independent performance estimate.",
        ],
        "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__},
    }
    suffix = "" if profile == "summary" else f"_{profile}"
    root = output_dir or PROJECT_ROOT / "ml" / "data" / f"optimization_{held_out_task}{suffix}"
    with artifact_run(root) as published:
        (published / "results.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        rows = [
            {
                "participant_hash": hashlib.sha256(ids[i].encode()).hexdigest(),
                "fold": int(fold_ids[i]),
                "observed": int(labels[i]),
                "predicted": int(predictions[i]),
                "baseline": int(baseline[i]),
                "decision_score": float(scores[i]),
            }
            for i in range(len(labels))
        ]
        (published / "predictions.json").write_text(
            json.dumps(rows, indent=2) + "\n", encoding="utf-8"
        )
        cv = final_search.cv_results_
        ranking = sorted(
            [
                {"parameters": _description(p), "mean_accuracy": float(a), "std_accuracy": float(s)}
                for p, a, s in zip(cv["params"], cv["mean_test_accuracy"], cv["std_test_accuracy"])
            ],
            key=lambda item: item["mean_accuracy"],
            reverse=True,
        )
        (published / "selection_scores.json").write_text(
            json.dumps(ranking, indent=2) + "\n", encoding="utf-8"
        )
        (published / "weights_and_biases.json").write_text(
            json.dumps(
                {
                    "deployment": model_parameters(final_search.best_estimator_),
                    "outer_fold_models": fold_parameters,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        joblib.dump(
            {
                "pipeline": final_search.best_estimator_,
                "held_out_task": held_out_task,
                "feature_version": FEATURE_VERSION,
                "evaluation": result,
            },
            published / "predictor.joblib",
        )
    print(
        f"[optimize] nested accuracy={result['accuracy']:.3f} balanced={result['balanced_accuracy']:.3f} baseline={result['majority_baseline']:.3f}",
        flush=True,
    )
    print(f"[optimize] saved results and fitted predictor to {root}", flush=True)
    return result


def predict_sessions(artifact_path: Path, sessions: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """Predict using a trusted local joblib artifact; target trials are ignored."""
    artifact = joblib.load(resolve_artifact(artifact_path))
    if artifact["feature_version"] not in (1, FEATURE_VERSION):
        raise RuntimeError("Unsupported behavioral feature version.")
    return artifact["pipeline"].predict(
        [
            behavior_features(
                s, artifact["held_out_task"], include_mechanisms=artifact["feature_version"] >= 2
            )
            for s in sessions
        ]
    )
