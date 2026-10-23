"""Advanced experiments preserve target isolation and participant-level evaluation."""

import copy
from pathlib import Path
import tempfile
import unittest

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.utils.advanced_benchmark import (
    Candidate,
    fit_ensemble,
    predict_advanced,
    run_advanced_benchmark,
)
from ml.utils.advanced_features import AdvancedFeatureView, advanced_features
from test_ml_pipeline import session


def complete_risk(index):
    item = session(index)
    template = next(t for t in item["trials"] if t["task_id"] == "risk_pref")
    for position in range(7, 31):
        trial = copy.deepcopy(template)
        trial["trial_index"] = position
        item["trials"].append(trial)
    return item


class AdvancedBenchmarkTests(unittest.TestCase):
    def test_parameter_inspection_preserves_regression_coefficients(self):
        from sklearn.linear_model import Ridge
        from ml.utils.inspect_predictors import pipeline_parameters

        pipeline = Pipeline(
            [
                ("vectorize", DictVectorizer(sparse=False)),
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=1.0)),
            ]
        ).fit([{"a": 0.0, "b": 2.0}, {"a": 1.0, "b": 0.0}, {"a": 2.0, "b": 1.0}], [0.0, 0.5, 1.0])
        inspected = pipeline_parameters(pipeline)
        weights = {
            row["feature"]: row["weight"] for row in inspected["coefficients_after_preprocessing"]
        }
        np.testing.assert_allclose([weights["a"], weights["b"]], pipeline[-1].coef_)
        self.assertEqual(inspected["intercept"], pipeline[-1].intercept_)

    def test_covariate_views_and_precomputation_exclude_target_answers(self):
        from ml.utils.covariate_benchmark import CovariateFeatures

        item = complete_risk(0)
        item.update(age=16, school_class=10)
        prepared = CovariateFeatures("combined").fit_transform([item])
        hidden = copy.deepcopy(item)
        for trial in hidden["trials"]:
            if trial["task_id"] == "risk_pref":
                trial["action_taken"] = "hidden"
        for view in ("demographics", "behavior", "combined"):
            transformer = CovariateFeatures(view).fit([item])
            self.assertEqual(transformer.transform([item]), transformer.transform(prepared))
            self.assertEqual(transformer.transform([item]), transformer.transform([hidden]))
        demographics = CovariateFeatures("demographics").fit_transform([item])[0]
        self.assertTrue(all(key.startswith("context.") for key in demographics))
        self.assertFalse(
            any(
                key.startswith("context.")
                for key in CovariateFeatures("behavior").fit_transform([item])[0]
            )
        )

    def test_covariate_nested_artifacts_reload_with_raw_sessions(self):
        from unittest.mock import patch
        from ml.artifacts import resolve_artifact
        from ml.utils import covariate_benchmark as module
        import joblib

        sessions = [complete_risk(i) for i in range(18)]
        for i, item in enumerate(sessions):
            item.update(age=14 + i % 5, school_class=9 + i % 4)
        original_search = module._search

        def small_search(*args):
            search = original_search(*args)
            search.param_grid = {"model__C": [0.1]}
            return search

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(module, "_search", small_search),
        ):
            root = Path(directory)
            result = module.run_covariate_benchmark(
                sessions=sessions, output_dir=root, outer_folds=3, inner_folds=2, jobs=1
            )
            self.assertEqual(result["metrics"]["combined"]["n"], 18)
            models = joblib.load(resolve_artifact(root / "predictors.joblib"))
            self.assertEqual(models["combined"].predict(sessions).shape, (18,))
            np.testing.assert_array_equal(
                module.predict_covariates(root / "predictors.joblib", sessions),
                models["combined"].predict(sessions),
            )

    def test_nullable_role_specific_fields_are_encoded_without_nan(self):
        item = complete_risk(0)
        item["trials"].append(
            {
                "task_id": "social_ultimatum",
                "trial_index": 1,
                "action_taken": "50",
                "reaction_time_ms": 500,
                "state_vector": {"partner_offer": None, "endowment": 100},
                "reward_received": {"accepted": True},
            }
        )
        features = advanced_features(item)
        self.assertTrue(all(np.isfinite(v) for v in features.values() if not isinstance(v, str)))
        self.assertEqual(features["social_ultimatum.sequence.1.partner_offer_present"], 0.0)

    def test_features_ignore_every_target_field_and_order(self):
        original = complete_risk(1)
        changed = copy.deepcopy(original)
        changed.update(participant_id="different", age=99)
        for trial in changed["trials"]:
            if trial["task_id"] == "risk_pref":
                trial.update(
                    action_taken=object(),
                    reaction_time_ms=object(),
                    state_vector=object(),
                    reward_received=object(),
                )
        changed["trials"].reverse()
        self.assertEqual(advanced_features(original), advanced_features(changed))

    def test_ensemble_learns_nonnegative_weights_on_training_predictions(self):
        labels = np.array([0, 1] * 20)
        useful = np.where(labels, 0.9, 0.1)
        noise = np.full(len(labels), 0.5)
        weights, threshold = fit_ensemble(np.column_stack([useful, noise]), labels)
        self.assertTrue(np.all(weights >= 0))
        self.assertAlmostEqual(float(weights.sum()), 1.0)
        self.assertGreater(weights[0], weights[1])
        self.assertTrue(0.3 <= threshold <= 0.7)

    def test_nested_augmentation_and_predictor_roundtrip(self):
        def pipeline(model):
            return Pipeline(
                [
                    ("view", AdvancedFeatureView("summary")),
                    ("vector", DictVectorizer(sparse=False)),
                    ("scale", StandardScaler()),
                    ("model", model),
                ]
            )

        pool = [
            Candidate("logit", pipeline(LogisticRegression(C=1, max_iter=1000))),
            Candidate("logit-aux", pipeline(LogisticRegression(C=1, max_iter=1000)), True),
            Candidate("majority", pipeline(DummyClassifier(strategy="prior"))),
        ]
        sessions = [complete_risk(i) for i in range(18)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_advanced_benchmark(
                sessions=sessions,
                auxiliary_sessions=[complete_risk(99), sessions[0]],
                pool=pool,
                output_dir=root,
                outer_folds=3,
                inner_folds=2,
                repeats=1,
                jobs=1,
                include_tabpfn=False,
            )
            self.assertEqual(result["n_auxiliary_training_only"], 1)
            self.assertEqual(result["n_participants"], 18)
            self.assertEqual(len(result["folds"]), 3)
            self.assertGreater(result["metrics"]["weighted_ensemble"]["accuracy"], 0.8)
            prediction = predict_advanced(root / "predictor.joblib", sessions)
            hidden = copy.deepcopy(sessions)
            for item in hidden:
                for trial in item["trials"]:
                    if trial["task_id"] == "risk_pref":
                        trial["action_taken"] = "hidden"
            np.testing.assert_array_equal(
                prediction, predict_advanced(root / "predictor.joblib", hidden)
            )

    def test_rate_supervision_preserves_binary_evaluation_and_hidden_answers(self):
        from sklearn.linear_model import Ridge
        from ml.utils.rate_benchmark import RateCandidate, run_rate_benchmark, predict_rates

        pipeline = Pipeline(
            [
                ("view", AdvancedFeatureView("summary")),
                ("vector", DictVectorizer(sparse=False)),
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=1.0)),
            ]
        )
        pool = [RateCandidate("ridge", pipeline), RateCandidate("ridge-aux", pipeline, True)]
        sessions = [complete_risk(i) for i in range(18)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_rate_benchmark(
                sessions=sessions,
                auxiliary_sessions=[complete_risk(99), sessions[0]],
                pool=pool,
                output_dir=root,
                outer_folds=3,
                inner_folds=2,
                repeats=1,
                jobs=1,
            )
            self.assertEqual(result["n_auxiliary_training_only"], 1)
            self.assertEqual(result["metrics"]["rate_ensemble"]["n"], 18)
            prediction = predict_rates(root / "predictor.joblib", sessions)
            hidden = copy.deepcopy(sessions)
            for item in hidden:
                for trial in item["trials"]:
                    if trial["task_id"] == "risk_pref":
                        trial["action_taken"] = "hidden"
            np.testing.assert_array_equal(
                prediction, predict_rates(root / "predictor.joblib", hidden)
            )


if __name__ == "__main__":
    unittest.main()
