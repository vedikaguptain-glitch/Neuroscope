"""Export readable parameters from trusted, checksummed local predictors."""

from pathlib import Path

import joblib
import numpy as np

from ml.artifacts import artifact_run, resolve_artifact, write_json


def pipeline_parameters(pipeline):
    names = None
    for _, step in pipeline.steps[:-1]:
        if hasattr(step, "get_feature_names_out"):
            names = step.get_feature_names_out(names)
    estimator = pipeline.steps[-1][1]
    result = {"estimator": type(estimator).__name__}
    if hasattr(estimator, "coef_"):
        coefficients = np.asarray(estimator.coef_).reshape(-1)
        if names is not None and len(names) == len(coefficients):
            result["coefficients_after_preprocessing"] = sorted(
                [{"feature": str(k), "weight": float(v)} for k, v in zip(names, coefficients)],
                key=lambda item: abs(item["weight"]),
                reverse=True,
            )
        else:
            result["coefficient_matrix"] = np.asarray(estimator.coef_).tolist()
        result["intercept"] = np.asarray(estimator.intercept_).tolist()
    if hasattr(estimator, "feature_importances_"):
        importance = np.asarray(estimator.feature_importances_)
        if names is not None and len(names) == len(importance):
            result["feature_importances"] = sorted(
                [{"feature": str(k), "importance": float(v)} for k, v in zip(names, importance)],
                key=lambda item: item["importance"],
                reverse=True,
            )
    result["interpretation"] = (
        "Parameters of the full-cohort deployment fit, not held-out effects. "
        "Coefficients apply after pipeline preprocessing; tree importances are estimator-specific. "
        "These associations do not establish causal behavioral effects."
    )
    return result


def export_parameters(root, predictor_name="predictor.joblib"):
    root = Path(root)
    predictor = joblib.load(resolve_artifact(root / predictor_name))
    if isinstance(predictor, dict):
        result = {name: pipeline_parameters(model) for name, model in predictor.items()}
    else:
        result = {
            "threshold": float(predictor.threshold),
            "models": [
                {"ensemble_weight": float(weight), **pipeline_parameters(model)}
                for model, weight in zip(predictor.models, predictor.weights)
            ],
        }
    with artifact_run(root / "inspection") as published:
        write_json(published / "weights_and_biases.json", result)
    return result
