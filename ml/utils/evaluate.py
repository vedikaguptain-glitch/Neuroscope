"""Linear probing of frozen embeddings for held-out task generalization."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report
from sklearn.model_selection import LeaveOneOut, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import torch

from ml.utils.dataset import BehavioralSequenceDataset
from ml.utils.infer import extract_hidden_states, load_trained_model, pool_hidden_states
from ml.utils.preprocess import TASK_ORDER, Vocab

HELD_OUT_DEFAULT = "risk_pref"
POSITIVE_ACTION = {
    "risk_pref": "gamble",
    "delay_disc": "delayed",
    "social_ultimatum": "accept",
}


def _task_token_id(spec: Mapping[str, Any], task_name: str) -> int:
    task_vocab = spec["task_vocab"]
    if not isinstance(task_vocab, dict):
        raise TypeError("Feature spec is missing task_vocab.")
    if task_name not in task_vocab:
        raise RuntimeError(
            f"Unknown task '{task_name}'. Expected one of: {', '.join(TASK_ORDER)}."
        )
    return Vocab.from_dict(task_vocab).encode(task_name)


def _binary_or_majority_labels(
    action: torch.Tensor,
    task_id: torch.Tensor,
    attention_mask: torch.Tensor,
    held_out_id: int,
    action_vocab: Vocab,
    held_out_task: str,
) -> np.ndarray:
    positive_name = POSITIVE_ACTION.get(held_out_task)
    positive_id = action_vocab.encode(positive_name) if positive_name else None
    if positive_name is not None and positive_name not in action_vocab.token_to_id:
        positive_id = None

    labels: list[int] = []
    pad_id = action_vocab.encode(None)
    for index in range(action.shape[0]):
        selected = (
            attention_mask[index].bool()
            & (task_id[index] == held_out_id)
            & (action[index] != pad_id)
        )
        chosen = action[index][selected]
        if chosen.numel() == 0:
            labels.append(-1)
            continue
        if positive_id is not None:
            rate = float((chosen == positive_id).float().mean())
            labels.append(1 if rate >= 0.5 else 0)
        else:
            values, counts = torch.unique(chosen, return_counts=True)
            labels.append(int(values[int(torch.argmax(counts))].item()))
    return np.asarray(labels, dtype=np.int64)


def _probe_split(
    features: np.ndarray,
    labels: np.ndarray,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    n = features.shape[0]
    unique, counts = np.unique(labels, return_counts=True)
    if unique.size < 2:
        raise RuntimeError(
            "Held-out labels are constant across participants, so linear probing is undefined."
        )

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=seed,
                ),
            ),
        ]
    )

    # Too few samples, or a class with a single example: use leave-one-out.
    if n < 6 or int(counts.min()) < 2:
        loo = LeaveOneOut()
        preds = np.zeros_like(labels)
        for train_idx, test_idx in loo.split(features):
            if np.unique(labels[train_idx]).size < 2:
                majority = int(np.bincount(labels[train_idx]).argmax())
                preds[test_idx] = majority
                continue
            pipeline.fit(features[train_idx], labels[train_idx])
            preds[test_idx] = pipeline.predict(features[test_idx])
        return labels, preds

    stratify = labels if int(counts.min()) >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.3,
        random_state=seed,
        stratify=stratify,
    )
    pipeline.fit(x_train, y_train)
    return y_test, pipeline.predict(x_test)


def run_evaluation(
    *,
    held_out_task: str = HELD_OUT_DEFAULT,
    seed: int = 42,
    dataset: BehavioralSequenceDataset | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    """Probe frozen embeddings (excluding the held-out task) to predict that task's behavior."""
    model = load_trained_model(checkpoint_path)
    data = dataset or BehavioralSequenceDataset.from_processed_file()
    if len(data) == 0:
        raise RuntimeError("No processed sequences found. Run `python main.py --extract` first.")

    held_out_id = _task_token_id(data.spec, held_out_task)
    action_vocab = Vocab.from_dict(data.spec["action_vocab"])

    hidden_rows: list[torch.Tensor] = []
    other_masks: list[torch.Tensor] = []
    for index in range(len(data)):
        item = data[index]
        other_mask = item["attention_mask"].clone()
        other_mask[item["task_id"] == held_out_id] = 0
        hidden = extract_hidden_states(
            model,
            item["state"].unsqueeze(0),
            item["action"].unsqueeze(0),
            item["reward"].unsqueeze(0),
            item["delta_t"].unsqueeze(0),
            item["task_id"].unsqueeze(0),
            other_mask.unsqueeze(0),
        )
        hidden_rows.append(hidden.squeeze(0).cpu())
        other_masks.append(other_mask.cpu())

    hidden_states = torch.stack(hidden_rows, dim=0)
    other_mask = torch.stack(other_masks, dim=0)
    if int(other_mask.sum()) == 0:
        raise RuntimeError("No non-held-out trials available to form probe features.")

    features = pool_hidden_states(hidden_states, other_mask).numpy()
    labels = _binary_or_majority_labels(
        data.action,
        data.task_id,
        (data.action != data.pad_action_id).to(torch.long),
        held_out_id,
        action_vocab,
        held_out_task,
    )
    valid = labels >= 0
    features = features[valid]
    labels = labels[valid]
    if labels.size == 0:
        raise RuntimeError(f"No {held_out_task} trials found to build probe labels.")

    y_true, y_pred = _probe_split(features, labels, seed)
    majority = int(np.bincount(labels).argmax())
    baseline = float((y_true == majority).mean()) if y_true.size else 0.0
    metrics = {
        "held_out_task": held_out_task,
        "n_participants": int(labels.size),
        "n_eval": int(y_true.size),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "majority_baseline": baseline,
        "feature_dim": int(features.shape[1]),
        "report": classification_report(y_true, y_pred, zero_division=0),
    }
    print(
        "[evaluate] "
        f"held_out={held_out_task} n={metrics['n_participants']} "
        f"acc={metrics['accuracy']:.3f} "
        f"balanced={metrics['balanced_accuracy']:.3f} "
        f"baseline={metrics['majority_baseline']:.3f}"
    )
    print(metrics["report"])
    return metrics
