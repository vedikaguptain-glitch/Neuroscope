"""Dependency-free paths and protocol constants shared by pipeline components."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "ml" / "data"
RAW_PARTICIPANTS_PATH = DATA_DIR / "raw_participants.json"
PROCESSED_PATH = DATA_DIR / "processed.pt"
VOCAB_PATH = DATA_DIR / "vocab.json"
CHECKPOINT_PATH = PROJECT_ROOT / "ml" / "models" / "neuroscope_msm.pt"
TASK_COUNTS = {
    "prob_learning": 60,
    "risk_pref": 30,
    "delay_disc": 50,
    "rule_discovery": 60,
    "social_ultimatum": 40,
}
TASK_ORDER = tuple(TASK_COUNTS)
SEQUENCE_LENGTH = sum(TASK_COUNTS.values())


def validate_cv(labels, outer_folds: int, inner_folds: int, jobs: int) -> None:
    """Reject unusable folds before starting an expensive search."""
    from collections import Counter

    counts = Counter(labels)
    if outer_folds < 2 or inner_folds < 2 or jobs < 1:
        raise RuntimeError("Cross-validation needs at least two folds and positive jobs.")
    if len(counts) != 2 or min(counts.values()) < outer_folds:
        raise RuntimeError("Too few participants per class for outer cross-validation.")
    smallest_training_class = min(
        count - (count + outer_folds - 1) // outer_folds for count in counts.values()
    )
    if smallest_training_class < inner_folds:
        raise RuntimeError("Too few training participants per class for inner cross-validation.")
