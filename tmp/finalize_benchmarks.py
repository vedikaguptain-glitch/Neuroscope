"""Verify the retained cohort and publish the exploratory benchmark comparison."""

from pathlib import Path
import copy
import json

import joblib
import numpy as np

from ml.artifacts import resolve_artifact, write_json
from ml.records import load_raw_participants
from ml.utils.inspect_predictors import export_parameters


root = Path("ml/data")
comparison = json.loads((root / "optimization_comparison.json").read_text())
comparison["experiments"] = comparison["experiments"][:3]
base = json.loads((root / "optimization_risk_pref/predictions.json").read_text())


def identity(rows):
    return [(r["participant_hash"], r["fold"], r["observed"]) for r in rows]


sessions = load_raw_participants()
for directory, model_file in (
    ("optimization_advanced_risk_pref", "predictor.joblib"),
    ("optimization_risk_rate", "predictor.joblib"),
    ("optimization_covariate_risk", "predictors.joblib"),
):
    experiment = root / directory
    results = json.loads(resolve_artifact(experiment / "results.json").read_text())
    rows = json.loads(resolve_artifact(experiment / "predictions.json").read_text())
    assert identity(rows) == identity(base), directory
    assert results["data_sha256"] == comparison["same_data_sha256"], directory
    for arm, metrics in results["metrics"].items():
        correct = sum(row["observed"] == row["predictions"][arm] for row in rows)
        assert correct == metrics["correct"] and len(rows) == metrics["n"] == 156
        comparison["experiments"].append(
            {
                "experiment": directory + ":" + arm,
                "uses_demographics": directory == "optimization_covariate_risk"
                and arm != "behavior",
                "known_target_stimuli": False,
                **metrics,
                "results_file": str(experiment / "results.json"),
            }
        )
    model = joblib.load(resolve_artifact(experiment / model_file))
    models = model.values() if isinstance(model, dict) else [model]
    hidden = copy.deepcopy(sessions[:3])
    for session in hidden:
        for trial in session["trials"]:
            if trial["task_id"] == "risk_pref":
                trial["action_taken"] = "hidden"
    for fitted in models:
        first, second = fitted.predict(sessions[:3]), fitted.predict(hidden)
        assert np.array_equal(first, second) and len(first) == 3
    export_parameters(experiment, model_file)
    if directory == "optimization_advanced_risk_pref":
        assert not results["deployment_errors"]
        assert all(not fold["errors"] for fold in results["folds"])

comparison.update(
    target_accuracy=0.85,
    target_required_correct=133,
    target_met=False,
    best_behavior_only_correct=105,
    best_with_context_correct=107,
    participant_provenance="Unverified: human, simulated or mixed origin not established.",
    conclusion=(
        "The 85% target was not reached. Best behavior-only accuracy is 105/156 (67.3%); "
        "including recorded age/class reaches 107/156 (68.6%), a different input scope. "
        "Retain the incumbent default pending independent confirmation."
    ),
)
write_json(root / "optimization_comparison.json", comparison)
print(
    "Verified matching cohort, labels and folds, all held-out counts, saved-model checksums and inference; no failed advanced candidates."
)
print(comparison["conclusion"])
