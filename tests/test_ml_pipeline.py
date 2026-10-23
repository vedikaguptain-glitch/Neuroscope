"""Leakage, preprocessing and checkpoint regression tests using synthetic records."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.base import clone
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import torch

from ml.utils.dataset import BehavioralSequenceDataset
from ml.utils.msm import msm_loss
from ml.utils.optimize import (
    behavior_features,
    candidate_search,
    model_parameters,
    predict_sessions,
    run_optimization,
    target_label,
)
from ml.utils.behavioral_models import FeatureView, fit_choice_weights
from ml.utils.preprocess import feature_dimension, fit_feature_spec, preprocess_sessions
from ml.utils.train import run_training


def session(index=0):
    return {
        "participant_id": f"synthetic-{index}",
        "age": 13 + index % 5,
        "trials": [
            {
                "task_id": "prob_learning",
                "trial_index": j + 1,
                "action_taken": "A" if index % 2 else "B",
                "state_vector": {"amount": j, "symbol": "square" if j % 2 else "circle"},
                "reward_received": {"points": j % 2, "outcome": "reward" if j % 2 else "lose"},
                "reaction_time_ms": 300 + 10 * index + j,
            }
            for j in range(6)
        ]
        + [
            {
                "task_id": "risk_pref",
                "trial_index": j + 1,
                "action_taken": "gamble" if index % 2 else "safe",
                "state_vector": {
                    "gamble_probability": 0.5,
                    "gamble_win_amount": 100,
                    "safe_amount": 50,
                },
                "reward_received": {"points": 50},
                "reaction_time_ms": 500,
            }
            for j in range(6)
        ],
    }


class FeatureIsolationTests(unittest.TestCase):
    def test_target_trials_and_demographics_cannot_change_features(self):
        original = session()
        changed = copy.deepcopy(original)
        changed.update(
            age=99, school_class=1, participant_id="different", session_started_at="changed"
        )
        for trial in changed["trials"]:
            if trial["task_id"] == "risk_pref":
                trial.update(
                    action_taken="gamble",
                    reward_received={"points": 1000000},
                    reaction_time_ms=1,
                    state_vector={"secret": 123},
                )
        self.assertEqual(
            behavior_features(original, "risk_pref"), behavior_features(changed, "risk_pref")
        )
        changed["trials"] = [t for t in changed["trials"] if t["task_id"] != "risk_pref"]
        self.assertEqual(
            behavior_features(original, "risk_pref"), behavior_features(changed, "risk_pref")
        )

    def test_target_threshold_and_social_roles(self):
        item = session()
        risk = [t for t in item["trials"] if t["task_id"] == "risk_pref"]
        for trial in risk[:3]:
            trial["action_taken"] = "gamble"
        self.assertEqual(target_label(item, "risk_pref"), 1)
        risk[0]["action_taken"] = "safe"
        self.assertEqual(target_label(item, "risk_pref"), 0)
        social = {
            "trials": [
                {"task_id": "social_ultimatum", "action_taken": a}
                for a in ["50", "20", "10", "accept", "reject"]
            ]
        }
        self.assertEqual(target_label(social, "social_ultimatum"), 1)

    def test_nested_predictions_and_roundtrip(self):
        def small_search(seed, inner_folds, jobs, held_out_task="risk_pref", profile="summary"):
            return GridSearchCV(
                make_pipeline(
                    DictVectorizer(sparse=False),
                    StandardScaler(),
                    LogisticRegression(max_iter=1000),
                ),
                {"logisticregression__C": [0.01, 1]},
                cv=StratifiedKFold(inner_folds, shuffle=True, random_state=seed),
                scoring={"accuracy": "accuracy"},
                refit="accuracy",
            )

        sessions = [session(i) for i in range(18)]
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("ml.utils.optimize.candidate_search", small_search),
        ):
            root = Path(directory)
            metrics = run_optimization(
                sessions=sessions, output_dir=root, outer_folds=3, inner_folds=2, jobs=1
            )
            rows = json.loads((root / "predictions.json").read_text())
            self.assertEqual(len(rows), 18)
            self.assertEqual(len({r["participant_hash"] for r in rows}), 18)
            self.assertEqual({r["fold"] for r in rows}, {1, 2, 3})
            self.assertTrue(all(f["n_train"] == 12 and f["n_test"] == 6 for f in metrics["folds"]))
            self.assertGreater(metrics["accuracy"], 0.8)
            predicted = predict_sessions(root / "predictor.joblib", sessions)
            hidden = copy.deepcopy(sessions)
            for item in hidden:
                item["trials"] = [t for t in item["trials"] if t["task_id"] != "risk_pref"]
            np.testing.assert_array_equal(
                predicted, predict_sessions(root / "predictor.joblib", hidden)
            )

    def test_duplicate_participants_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "distinct"):
            run_optimization(sessions=[session(), session()])


class RepresentationTests(unittest.TestCase):
    def test_training_spec_and_missingness(self):
        training = session()
        spec = fit_feature_spec([training])
        self.assertEqual(spec["version"], 2)
        expected = copy.deepcopy(spec)
        unseen = session(1)
        unseen["trials"][0]["state_vector"] = {"amount": 1000000, "symbol": "never-seen"}
        unseen["trials"][0]["reward_received"] = {}
        bundle = preprocess_sessions([unseen], spec)
        self.assertEqual(spec, expected)
        self.assertEqual(bundle["state"].shape[-1], feature_dimension(spec, "state"))
        self.assertEqual(bundle["reward"].shape[-1], feature_dimension(spec, "reward"))
        self.assertEqual(bundle["reward_observed"][0, 0].sum(), 0)
        self.assertTrue(torch.isfinite(bundle["state"]).all())
        self.assertLessEqual(float(bundle["state"].abs().max()), 10)
        self.assertEqual(float(bundle["reward_observed"][0, 239].sum()), 0)

    def test_absent_rewards_do_not_contribute_to_loss(self):
        action_logits = torch.zeros(1, 1, 2)
        prediction = torch.tensor([[[2.0, 9999.0]]])
        target = torch.zeros_like(prediction)
        mask = torch.ones(1, 1, dtype=torch.bool)
        _, logs = msm_loss(
            action_logits,
            prediction,
            torch.zeros(1, 1, dtype=torch.long),
            target,
            ~mask,
            mask,
            torch.tensor([[[1.0, 0.0]]]),
        )
        self.assertEqual(float(logs["loss_reward"]), 4.0)

    def test_best_epoch_saved_and_validation_randomness_fixed(self):
        data = BehavioralSequenceDataset.from_bundle(
            preprocess_sessions([session(i) for i in range(6)])
        )
        validation_losses = iter([1.0, 0.5, 0.8])
        validation_draws = []

        def fake_loss(model, loader, optimizer, max_grad_norm):
            if optimizer is None:
                validation_draws.append(float(torch.rand(())))
                loss = next(validation_losses)
            else:
                optimizer.step()
                loss = 2.0
            return {"loss": loss, "loss_action": loss, "loss_reward": 0.0, "n": 1.0}

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("ml.utils.train._mean_msm_loss", fake_loss),
        ):
            path = Path(directory) / "model.pt"
            run_training(epochs=3, dataset=data, checkpoint_path=path)
            saved = torch.load(path, weights_only=False, map_location="cpu")
            self.assertEqual(saved["epoch"], 2)
            self.assertEqual(saved["metrics"]["val_loss"], 0.5)
            self.assertEqual(len(set(validation_draws)), 1)


class BehavioralWeightTests(unittest.TestCase):
    def test_choice_coefficient_recovery_and_separation(self):
        from scipy.special import expit

        rng = np.random.default_rng(123)
        design = rng.normal(size=(2000, 2))
        true_weights = np.array([0.6, 0.8, -1.2])
        choices = rng.binomial(1, expit(np.column_stack([np.ones(2000), design]) @ true_weights))
        recovered = fit_choice_weights(design, choices)
        np.testing.assert_allclose(recovered, true_weights, atol=0.2)
        all_positive = fit_choice_weights(np.zeros((20, 2)), np.ones(20))
        self.assertTrue(np.isfinite(all_positive).all())
        self.assertGreater(all_positive[0], 0)
        self.assertLess(all_positive[0], 5)

    def test_feature_views_exclude_target_and_separate_families(self):
        features = behavior_features(session(), "risk_pref")
        for mode in ("summary", "mechanism", "all"):
            selected = FeatureView(mode=mode).fit_transform([features])[0]
            self.assertFalse(any(key.startswith("risk_pref.") for key in selected))
            if mode != "all":
                self.assertTrue(
                    all((".mechanism." in key) == (mode == "mechanism") for key in selected)
                )

    def test_stacking_and_threshold_predictor_roundtrips(self):
        import joblib
        from sklearn.ensemble import StackingClassifier
        from sklearn.model_selection import TunedThresholdClassifierCV
        from threadpoolctl import threadpool_limits

        search = candidate_search(42, 2, 1, held_out_task="risk_pref", profile="behavioral")
        candidates = [
            group["model"][0]
            for group in search.param_grid
            if isinstance(group["model"][0], (StackingClassifier, TunedThresholdClassifierCV))
        ]
        sessions = [session(i) for i in range(24)]
        features = [behavior_features(s, "risk_pref") for s in sessions]
        labels = [target_label(s, "risk_pref") for s in sessions]
        with tempfile.TemporaryDirectory() as directory, threadpool_limits(limits=1):
            for candidate in candidates:
                if isinstance(candidate, StackingClassifier):
                    self.assertNotIn("risk_pref", [name for name, _ in candidate.estimators])
                model = clone(candidate).fit(features, labels)
                predicted = model.predict(features)
                self.assertEqual(len(predicted), 24)
                parameters = model_parameters(model)
                json.dumps(parameters)
                path = Path(directory) / "model.joblib"
                joblib.dump(model, path)
                np.testing.assert_array_equal(predicted, joblib.load(path).predict(features))


class ConditionalPolicyTests(unittest.TestCase):
    def test_nested_conditional_artifacts_and_context_baseline(self):
        import joblib
        from ml.utils.conditional_policy import ConditionalRiskPolicy, run_conditional_policy

        def small_search(seed, inner_folds, jobs):
            return GridSearchCV(
                ConditionalRiskPolicy(seed=seed),
                {
                    "C": [0.01],
                    "view": ["context", "all"],
                    "interactions": [False],
                    "decision_threshold": [0.5],
                },
                scoring="accuracy",
                cv=StratifiedKFold(inner_folds, shuffle=True, random_state=seed),
            )

        sessions = [session(i) for i in range(18)]
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("ml.utils.conditional_policy._search", small_search),
        ):
            root = Path(directory)
            results = run_conditional_policy(
                sessions=sessions, output_dir=root, outer_folds=3, inner_folds=2, jobs=1
            )
            self.assertGreater(results["accuracy"], results["context_only_accuracy"])
            rows = json.loads((root / "predictions.json").read_text())
            self.assertEqual(len({r["participant_hash"] for r in rows}), 18)
            self.assertEqual({r["fold"] for r in rows}, {1, 2, 3})
            model = joblib.load(root / "predictor.joblib")["model"]
            self.assertEqual(model.predict(sessions).shape, (18,))
            json.loads((root / "weights_and_biases.json").read_text())

    def test_count_probability_at_exact_half(self):
        from ml.utils.conditional_policy import count_probability

        self.assertAlmostEqual(count_probability(np.array([0.5, 0.5])), 0.75)
        self.assertAlmostEqual(count_probability(np.array([1.0, 0.0])), 1.0)
        self.assertAlmostEqual(count_probability(np.zeros(30)), 0.0)

    def test_predictions_ignore_risk_answers_but_use_known_stimuli(self):
        from ml.utils.conditional_policy import ConditionalRiskPolicy

        sessions = [session(i) for i in range(18)]
        labels = [target_label(s, "risk_pref") for s in sessions]
        model = ConditionalRiskPolicy(view="all", interactions=True).fit(sessions, labels)
        original = model.predict_proba(sessions)
        changed = copy.deepcopy(sessions)
        for item in changed:
            item.update(age=99, school_class=1, participant_id="hidden")
            for trial in item["trials"]:
                if trial["task_id"] == "risk_pref":
                    trial.update(
                        action_taken=object(), reward_received=object(), reaction_time_ms=object()
                    )
        np.testing.assert_array_equal(original, model.predict_proba(changed))
        self.assertTrue(np.isfinite(original).all())
        json.dumps(model.weights())
        rng = np.random.default_rng(123)
        responsive = []
        for i in range(24):
            item = session(i)
            for trial in item["trials"]:
                if trial["task_id"] == "risk_pref":
                    trial["state_vector"]["gamble_win_amount"] = float(rng.choice([20, 300]))
                    trial["action_taken"] = (
                        "gamble" if trial["state_vector"]["gamble_win_amount"] == 300 else "safe"
                    )
            responsive.append(item)
        context_model = ConditionalRiskPolicy(view="context", C=1).fit(
            responsive, [target_label(s, "risk_pref") for s in responsive]
        )
        low, high = copy.deepcopy(sessions[:1]), copy.deepcopy(sessions[:1])
        for population, amount in ((low, 20), (high, 300)):
            for trial in population[0]["trials"]:
                if trial["task_id"] == "risk_pref":
                    trial["state_vector"]["gamble_win_amount"] = amount
        self.assertGreater(
            context_model.predict_proba(high)[0, 1], context_model.predict_proba(low)[0, 1]
        )


if __name__ == "__main__":
    unittest.main()
