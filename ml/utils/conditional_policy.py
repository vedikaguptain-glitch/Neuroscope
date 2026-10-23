"""Predict risk choices conditional on offered gambles and other-task behavior.

Unlike strict cross-task prediction, this experiment knows the target task's
exogenous stimuli at inference. Risk actions, outcomes and response times are
read only by fit(), never by predict()/predict_proba(). Splits are participants.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import joblib
from ml.artifacts import artifact_run
import numpy as np
from joblib import parallel_backend
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted
from threadpoolctl import threadpool_limits

from ml.utils.behavioral_models import FeatureView
from ml.config import PROJECT_ROOT, validate_cv
from ml.utils.features import behavior_features, target_label
from ml.records import load_raw_participants, validate_sessions


@lru_cache(maxsize=2048)
def _cached_behavior(nonrisk_trials_json):
    # Reuse only pure, participant-local calculations across training folds.
    return behavior_features({"trials": json.loads(nonrisk_trials_json)}, "risk_pref")


def _behavior_signature(session):
    keys = (
        "task_id",
        "trial_index",
        "state_vector",
        "action_taken",
        "reward_received",
        "reaction_time_ms",
    )
    trials = [
        {key: trial.get(key) for key in keys}
        for trial in session.get("trials", [])
        if trial.get("task_id") != "risk_pref"
    ]
    return json.dumps(trials, sort_keys=True, default=str)


def count_probability(probabilities: np.ndarray) -> float:
    """P(at least half the choices are gambles), assuming conditional independence."""
    distribution = np.array([1.0])
    for p in probabilities:
        distribution = np.convolve(distribution, [1 - p, p])
    return float(distribution[(len(probabilities) + 1) // 2 :].sum())


def risk_stimuli(session):
    trials = sorted(
        [t for t in session.get("trials", []) if t.get("task_id") == "risk_pref"],
        key=lambda trial: trial["trial_index"],
    )
    if not trials:
        raise ValueError("Conditional risk prediction requires the proposed risk-task stimuli.")
    stimuli = []
    for trial in trials:
        state = trial.get("state_vector") or {}
        p, win, safe = [
            float(state[key]) for key in ("gamble_probability", "gamble_win_amount", "safe_amount")
        ]
        if not np.isfinite([p, win, safe]).all() or not 0 <= p <= 1 or win < 0 or safe <= 0:
            raise ValueError("Invalid gamble probability or payoff.")
        stimuli.append(
            {
                "stimulus.ev_advantage": (p * win - safe) / 100,
                "stimulus.probability": p - 0.5,
                "stimulus.win": win / 100,
                "stimulus.variance": p * (1 - p) * (win / 100) ** 2,
                "stimulus.log_payoff_ratio": float(np.log(max(win, 1) / safe)),
                "stimulus.safe_on_left": float(state.get("safe_side") == "left") - 0.5,
            }
        )
    return trials, stimuli


class ConditionalRiskPolicy(ClassifierMixin, BaseEstimator):
    """Regularized trial policy with behavior-dependent intercept and EV slope."""

    def __init__(
        self,
        C: float = 0.01,
        view: str = "summary",
        interactions: bool = False,
        decision_threshold: float = 0.5,
        seed: int = 42,
    ):
        self.C = C
        self.view = view
        self.interactions = interactions
        self.decision_threshold = decision_threshold
        self.seed = seed

    def _design(self, sessions):
        rows, sizes = [], []
        for session in sessions:
            _, stimuli = risk_stimuli(session)
            sizes.append(len(stimuli))
            if self.view == "context":
                behavior = {}
            else:
                behavior = FeatureView(self.view).fit_transform(
                    [_cached_behavior(_behavior_signature(session))]
                )[0]
            for stimulus in stimuli:
                row = {**behavior, **stimulus}
                if self.interactions:
                    row.update(
                        {
                            f"ev_x_behavior.{key}": value * stimulus["stimulus.ev_advantage"]
                            for key, value in behavior.items()
                        }
                    )
                rows.append(row)
        return rows, sizes

    def fit(self, X, y):
        if (
            self.view not in ("summary", "mechanism", "all", "context")
            or not 0 < self.decision_threshold < 1
        ):
            raise ValueError("Invalid feature view or decision threshold.")
        labels = []
        for session, expected in zip(X, y):
            if target_label(session, "risk_pref") != expected:
                raise ValueError("Participant labels disagree with training trial responses.")
            trials, _ = risk_stimuli(session)
            actions = [trial["action_taken"] for trial in trials]
            if any(action not in ("safe", "gamble") for action in actions):
                raise ValueError("Training risk actions must be safe or gamble.")
            labels.extend(int(action == "gamble") for action in actions)
        if len(np.unique(labels)) < 2:
            raise ValueError("Both training choice classes are required.")
        rows, _ = self._design(X)
        self.vectorizer_ = DictVectorizer(sparse=False)
        self.scaler_ = StandardScaler()
        matrix = self.scaler_.fit_transform(self.vectorizer_.fit_transform(rows))
        self.policy_ = LogisticRegression(C=self.C, max_iter=2500, random_state=self.seed)
        self.policy_.fit(matrix, labels)
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        check_is_fitted(self, "policy_")
        rows, sizes = self._design(X)
        matrix = self.scaler_.transform(self.vectorizer_.transform(rows))
        trial_probs = self.policy_.predict_proba(matrix)[:, 1]
        positive, offset = [], 0
        for size in sizes:
            positive.append(count_probability(trial_probs[offset : offset + size]))
            offset += size
        return np.column_stack([1 - np.array(positive), positive])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= self.decision_threshold).astype(int)

    def weights(self):
        check_is_fitted(self, "policy_")
        names = self.vectorizer_.get_feature_names_out()
        weights = self.policy_.coef_[0]
        return {
            "intercept": float(self.policy_.intercept_[0]),
            "participant_probability_threshold": self.decision_threshold,
            "additional_participant_log_odds_bias": float(
                -np.log(self.decision_threshold / (1 - self.decision_threshold))
            ),
            "coefficients": sorted(
                [
                    {
                        "feature": str(name),
                        "standardized_weight": float(weight),
                        "training_mean": float(mean),
                        "training_sd": float(sd),
                    }
                    for name, weight, mean, sd in zip(
                        names, weights, self.scaler_.mean_, self.scaler_.scale_
                    )
                ],
                key=lambda item: abs(item["standardized_weight"]),
                reverse=True,
            ),
            "interpretation": "Prediction associations with conditional choice log odds, not established causal effects or psychological traits.",
        }


def _search(seed, inner_folds, jobs):
    grid = [
        {
            "view": ["context"],
            "C": [0.001, 0.01, 0.1, 1, 10],
            "interactions": [False],
            "decision_threshold": [0.4, 0.5, 0.6],
        },
        {
            "view": ["summary", "mechanism", "all"],
            "C": [0.001, 0.01, 0.1],
            "interactions": [False, True],
            "decision_threshold": [0.4, 0.5, 0.6],
        },
    ]
    return GridSearchCV(
        ConditionalRiskPolicy(seed=seed),
        grid,
        scoring="accuracy",
        cv=StratifiedKFold(inner_folds, shuffle=True, random_state=seed),
        n_jobs=jobs,
        error_score="raise",
    )


def run_conditional_policy(
    *, sessions=None, output_dir: Path | None = None, seed=42, outer_folds=5, inner_folds=3, jobs=4
):
    sessions = list(sessions) if sessions is not None else load_raw_participants()
    ids = [str(s.get("participant_id", "")) for s in sessions]
    if not sessions or any(not i for i in ids) or len(set(ids)) != len(ids):
        raise RuntimeError("Conditional policy requires unique participant IDs.")
    if outer_folds < 2 or inner_folds < 2 or jobs < 1:
        raise RuntimeError("Cross-validation needs at least two folds and positive jobs.")
    validate_sessions(sessions)
    labels = np.array([target_label(s, "risk_pref") for s in sessions])
    if len(np.unique(labels)) != 2 or np.bincount(labels).min() < outer_folds:
        raise RuntimeError("Too few participants per class for outer cross-validation.")
    validate_cv(labels, outer_folds, inner_folds, jobs)
    predictions, context_predictions, baseline = [
        np.full(len(labels), -1, dtype=int) for _ in range(3)
    ]
    probabilities = np.zeros(len(labels))
    fold_ids = np.zeros(len(labels), dtype=int)
    folds = []
    with threadpool_limits(limits=1), parallel_backend("threading"):
        for fold, (train, test) in enumerate(
            StratifiedKFold(outer_folds, shuffle=True, random_state=seed).split(
                np.zeros(len(labels)), labels
            ),
            1,
        ):
            train_sessions, test_sessions = [
                [sessions[i] for i in indices] for indices in (train, test)
            ]
            if np.bincount(labels[train]).min() < inner_folds:
                raise RuntimeError("Too few participants per class for inner cross-validation.")
            search = _search(seed, inner_folds, jobs).fit(train_sessions, labels[train])
            cv = search.cv_results_
            context_indices = [
                i for i, parameters in enumerate(cv["params"]) if parameters["view"] == "context"
            ]
            best_context = max(context_indices, key=lambda i: cv["mean_test_score"][i])
            context = (
                clone(search.estimator)
                .set_params(**cv["params"][best_context])
                .fit(train_sessions, labels[train])
            )
            model = search.best_estimator_
            predictions[test] = model.predict(test_sessions)
            probabilities[test] = model.predict_proba(test_sessions)[:, 1]
            context_predictions[test] = context.predict(test_sessions)
            baseline[test] = np.bincount(labels[train]).argmax()
            fold_ids[test] = fold
            result = {
                "fold": fold,
                "selected": search.best_params_,
                "n_train": len(train),
                "n_test": len(test),
                "inner_selection_accuracy": float(search.best_score_),
                "accuracy": float(accuracy_score(labels[test], predictions[test])),
                "context_only_accuracy": float(
                    accuracy_score(labels[test], context_predictions[test])
                ),
            }
            folds.append(result)
            print(
                f"[conditional] fold={fold} selected={result['selected']} accuracy={result['accuracy']:.3f} context_only={result['context_only_accuracy']:.3f}",
                flush=True,
            )
        final = _search(seed, inner_folds, jobs).fit(sessions, labels)
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": "Nested participant cross-validation of a trial-level conditional policy; target stimuli known, target test responses hidden.",
        "target": "Gamble on at least half of risk trials, unchanged from the strict cross-task experiment.",
        "available_at_prediction": "Other-task behavior plus offered risk probabilities, payouts and safe-option position.",
        "excluded_at_prediction": "Risk actions, outcomes, reaction times, participant IDs and demographics.",
        "seed": seed,
        "outer_folds": outer_folds,
        "inner_folds": inner_folds,
        "n_participants": len(labels),
        "accuracy": float(accuracy_score(labels, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
        "auc": float(roc_auc_score(labels, probabilities)),
        "context_only_accuracy": float(accuracy_score(labels, context_predictions)),
        "majority_baseline": float(accuracy_score(labels, baseline)),
        "folds": folds,
        "deployment_selected": final.best_params_,
        "deployment_selection_cv_accuracy": float(final.best_score_),
        "data_sha256": hashlib.sha256(
            json.dumps(sessions, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "limitations": [
            "Exploratory analysis developed on an already inspected cohort; new-cohort confirmation is required.",
            "Different input information and training supervision from the strict cross-task experiment; scores are not directly interchangeable.",
            "Count probabilities assume conditionally independent trials and have not been externally calibrated.",
        ],
    }
    root = output_dir or PROJECT_ROOT / "ml" / "data" / "conditional_risk_policy"
    with artifact_run(root) as published:
        (published / "results.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        (published / "weights_and_biases.json").write_text(
            json.dumps(final.best_estimator_.weights(), indent=2) + "\n", encoding="utf-8"
        )
        rows = [
            {
                "participant_hash": hashlib.sha256(ids[i].encode()).hexdigest(),
                "fold": int(fold_ids[i]),
                "observed": int(labels[i]),
                "predicted": int(predictions[i]),
                "probability": float(probabilities[i]),
                "context_only": int(context_predictions[i]),
                "majority": int(baseline[i]),
            }
            for i in range(len(labels))
        ]
        (published / "predictions.json").write_text(
            json.dumps(rows, indent=2) + "\n", encoding="utf-8"
        )
        joblib.dump(
            {"model": final.best_estimator_, "evaluation": result}, published / "predictor.joblib"
        )
    print(
        f"[conditional] nested accuracy={result['accuracy']:.3f} balanced={result['balanced_accuracy']:.3f} context_only={result['context_only_accuracy']:.3f} majority={result['majority_baseline']:.3f}",
        flush=True,
    )
    return result
