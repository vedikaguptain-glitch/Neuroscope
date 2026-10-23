"""Measure apparent training fit alongside participant-held-out validation."""

from pathlib import Path
import hashlib
import json

import joblib
import numpy as np

from ml.artifacts import artifact_run, resolve_artifact, write_json
from ml.config import DATA_DIR
from ml.records import load_raw_participants
from ml.utils.features import target_label


def measure_saved_fit(data_dir=DATA_DIR):
    root = Path(data_dir)
    sessions = load_raw_participants(root / "raw_participants.json")
    data_hash = hashlib.sha256(
        json.dumps(sessions, sort_keys=True, default=str).encode()
    ).hexdigest()
    labels = np.asarray([target_label(s, "risk_pref") for s in sessions])
    measurements = []
    for directory, filename, views in (
        (
            "optimization_covariate_risk",
            "predictors.joblib",
            ["combined", "behavior", "demographics"],
        ),
        ("optimization_risk_rate", "predictor.joblib", ["rate_ensemble"]),
        ("optimization_advanced_risk_pref", "predictor.joblib", ["weighted_ensemble"]),
    ):
        experiment = root / directory
        results = json.loads(resolve_artifact(experiment / "results.json").read_text())
        if data_hash != results["data_sha256"]:
            raise ValueError("The recorded cohort differs from the fitted experiment.")
        model_path = resolve_artifact(experiment / filename)
        saved = joblib.load(model_path)
        for view in views:
            model = saved[view] if isinstance(saved, dict) else saved
            predictions = np.asarray(model.predict(sessions))
            if predictions.shape != labels.shape:
                raise ValueError("Incomplete fitted predictions.")
            correct = int(np.sum(predictions == labels))
            validation = results["metrics"][view]
            measurements.append(
                {
                    "experiment": directory,
                    "arm": view,
                    "metric_name": "training-set accuracy (apparent fit)",
                    "training_correct": correct,
                    "n": len(labels),
                    "training_accuracy": correct / len(labels),
                    "nested_cv_accuracy": validation["accuracy"],
                    "nested_cv_correct": validation["correct"],
                    "fit_validation_gap": correct / len(labels) - validation["accuracy"],
                    "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                }
            )
    result = {
        "data_sha256": data_hash,
        "measurements": measurements,
        "interpretation": (
            "Training-set accuracy measures fit on sessions already used in training. "
            "It does not estimate accuracy on new participants. The fit-validation gap "
            "shows optimism/overfitting; nested validation remains exploratory on this reused cohort."
        ),
        "participant_provenance": "Unverified: human, simulated or mixed origin not established.",
    }
    with artifact_run(root / "optimization_fit_diagnostics") as published:
        write_json(published / "results.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(measure_saved_fit(), indent=2))
