"""PyTorch dataset and loaders for 240-step behavioral sequences."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, Subset

from ml.utils.preprocess import (
    PAD_TOKEN,
    PROCESSED_PATH,
    SEQUENCE_LENGTH,
    FeatureSpec,
    Vocab,
    load_raw_participants,
    preprocess_raw_participants,
    preprocess_sessions,
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class BehavioralSequenceDataset(Dataset[dict[str, Any]]):
    """Yields padded 240-step x_t sequences for one participant each."""

    def __init__(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        reward: torch.Tensor,
        delta_t: torch.Tensor,
        task_id: torch.Tensor,
        x: torch.Tensor,
        participant_ids: Sequence[str],
        spec: FeatureSpec,
    ) -> None:
        if x.ndim != 3 or x.shape[1] != SEQUENCE_LENGTH:
            raise ValueError(
                f"Expected x with shape [N, {SEQUENCE_LENGTH}, D], got {tuple(x.shape)}."
            )
        n = x.shape[0]
        if not (
            state.shape[0]
            == action.shape[0]
            == reward.shape[0]
            == delta_t.shape[0]
            == task_id.shape[0]
            == len(participant_ids)
            == n
        ):
            raise ValueError("Sequence tensors and participant_ids must share length N.")

        self.state = state.cpu()
        self.action = action.cpu()
        self.reward = reward.cpu()
        self.delta_t = delta_t.cpu()
        self.task_id = task_id.cpu()
        self.x = x.cpu()
        self.participant_ids = list(participant_ids)
        self.spec = spec
        self.pad_action_id = Vocab.from_dict(spec["action_vocab"]).encode(PAD_TOKEN)

    def __len__(self) -> int:
        return int(self.x.shape[0])

    def __getitem__(self, index: int) -> dict[str, Any]:
        attention_mask = (self.action[index] != self.pad_action_id).to(torch.long)
        return {
            "participant_id": self.participant_ids[index],
            "state": self.state[index],
            "action": self.action[index],
            "reward": self.reward[index],
            "delta_t": self.delta_t[index],
            "task_id": self.task_id[index],
            "x": self.x[index],
            "attention_mask": attention_mask,
        }

    @classmethod
    def from_bundle(cls, bundle: Mapping[str, Any]) -> BehavioralSequenceDataset:
        spec = bundle["spec"]
        if not isinstance(spec, dict):
            raise ValueError("Processed bundle is missing a feature spec.")
        return cls(
            state=bundle["state"],
            action=bundle["action"],
            reward=bundle["reward"],
            delta_t=bundle["delta_t"],
            task_id=bundle["task_id"],
            x=bundle["x"],
            participant_ids=bundle["participant_ids"],
            spec=spec,
        )

    @classmethod
    def from_processed_file(
        cls,
        path: Path | None = None,
    ) -> BehavioralSequenceDataset:
        from ml.utils.preprocess import VOCAB_PATH

        source = path or PROCESSED_PATH
        if not source.exists():
            bundle = preprocess_raw_participants()
            return cls.from_bundle(bundle)

        payload = torch.load(source, map_location="cpu", weights_only=False)
        if VOCAB_PATH.exists():
            import json

            payload["spec"] = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
        if "spec" not in payload:
            sessions = load_raw_participants()
            payload["spec"] = preprocess_sessions(sessions)["spec"]
        return cls.from_bundle(payload)


def split_indices(
    n_samples: int,
    val_fraction: float = 0.2,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Participant-level train/validation split. Keeps at least one train item when n > 0."""
    if n_samples < 0:
        raise ValueError("n_samples must be non-negative.")
    if n_samples == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    if n_samples == 1:
        return np.array([0], dtype=np.int64), np.array([], dtype=np.int64)

    rng = np.random.default_rng(seed)
    permutation = rng.permutation(n_samples)
    n_val = int(round(n_samples * val_fraction))
    n_val = min(max(n_val, 1), n_samples - 1)
    val_idx = np.sort(permutation[:n_val])
    train_idx = np.sort(permutation[n_val:])
    return train_idx, val_idx


def make_dataloaders(
    dataset: BehavioralSequenceDataset,
    batch_size: int = 8,
    val_fraction: float = 0.2,
    seed: int = 42,
    num_workers: int = 0,
) -> tuple[DataLoader[dict[str, Any]], DataLoader[dict[str, Any]]]:
    train_idx, val_idx = split_indices(len(dataset), val_fraction=val_fraction, seed=seed)
    train_subset: Dataset[dict[str, Any]] = Subset(dataset, train_idx.tolist())
    val_subset: Dataset[dict[str, Any]] = Subset(dataset, val_idx.tolist())
    pin_memory = DEVICE.type == "cuda"

    train_loader = DataLoader(
        train_subset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=False,
    )
    val_loader = DataLoader(
        val_subset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=False,
    )
    return train_loader, val_loader
