"""Extract behavioral embeddings from a trained transformer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from ml.models.transformer import BehavioralTransformer
from ml.utils.dataset import BehavioralSequenceDataset, DEVICE
from ml.utils.db import PROJECT_ROOT
from ml.utils.train import CHECKPOINT_PATH

EMBEDDINGS_PATH = PROJECT_ROOT / "ml" / "data" / "embeddings.pt"


def load_trained_model(checkpoint_path: Path | None = None) -> BehavioralTransformer:
    """Load a BehavioralTransformer and its MSM heads from a training checkpoint."""
    source = checkpoint_path or CHECKPOINT_PATH
    if not source.exists():
        raise RuntimeError(
            f"No trained weights at {source}. Run `python main.py --train` first."
        )
    payload = torch.load(source, map_location="cpu", weights_only=False)
    spec = payload.get("spec")
    if not isinstance(spec, dict):
        raise RuntimeError("Checkpoint is missing the preprocessing spec.")
    config = payload.get("config") or {}
    model = BehavioralTransformer.from_spec(
        spec,
        d_model=int(config.get("d_model", 128)),
        nhead=int(config.get("nhead", 4)),
        num_layers=int(config.get("num_layers", 4)),
        dim_feedforward=int(config.get("dim_feedforward", 256)),
        dropout=float(config.get("dropout", 0.1)),
    )
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model


@torch.no_grad()
def extract_hidden_states(
    model: BehavioralTransformer,
    state: torch.Tensor,
    action: torch.Tensor,
    reward: torch.Tensor,
    delta_t: torch.Tensor,
    task_id: torch.Tensor,
    attention_mask: torch.Tensor | None = None,
) -> torch.Tensor:
    """Run a full 240-trial sequence (no MSM corruption) and return encoder states."""
    model.eval()
    return model.encode(
        state,
        action,
        reward,
        delta_t,
        task_id=task_id,
        attention_mask=attention_mask,
    )


def pool_hidden_states(
    hidden: torch.Tensor,
    attention_mask: torch.Tensor,
) -> torch.Tensor:
    """Mean-pool trial embeddings over non-padding timesteps."""
    mask = attention_mask.to(device=hidden.device, dtype=hidden.dtype).unsqueeze(-1)
    summed = (hidden * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1.0)
    return summed / counts


@torch.no_grad()
def extract_dataset_embeddings(
    model: BehavioralTransformer,
    dataset: BehavioralSequenceDataset,
    batch_size: int = 4,
) -> dict[str, Any]:
    """Collect per-trial hidden states and pooled session embeddings."""
    model.eval()
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=DEVICE.type == "cuda",
    )
    hidden_chunks: list[torch.Tensor] = []
    pooled_chunks: list[torch.Tensor] = []
    participant_ids: list[str] = []
    action_chunks: list[torch.Tensor] = []
    task_chunks: list[torch.Tensor] = []
    mask_chunks: list[torch.Tensor] = []

    for batch in loader:
        hidden = extract_hidden_states(
            model,
            batch["state"],
            batch["action"],
            batch["reward"],
            batch["delta_t"],
            batch["task_id"],
            batch["attention_mask"],
        )
        pooled = pool_hidden_states(hidden, batch["attention_mask"])
        hidden_chunks.append(hidden.cpu())
        pooled_chunks.append(pooled.cpu())
        participant_ids.extend(batch["participant_id"])
        action_chunks.append(batch["action"].cpu())
        task_chunks.append(batch["task_id"].cpu())
        mask_chunks.append(batch["attention_mask"].cpu())

    return {
        "participant_ids": participant_ids,
        "hidden_states": torch.cat(hidden_chunks, dim=0) if hidden_chunks else torch.empty(0),
        "pooled": torch.cat(pooled_chunks, dim=0) if pooled_chunks else torch.empty(0),
        "action": torch.cat(action_chunks, dim=0) if action_chunks else torch.empty(0),
        "task_id": torch.cat(task_chunks, dim=0) if task_chunks else torch.empty(0),
        "attention_mask": torch.cat(mask_chunks, dim=0) if mask_chunks else torch.empty(0),
    }


def extract_and_save_embeddings(
    checkpoint_path: Path | None = None,
    output_path: Path | None = None,
    dataset: BehavioralSequenceDataset | None = None,
    batch_size: int = 4,
) -> Path:
    """Load trained weights, embed every session, and write ml/data/embeddings.pt."""
    destination = output_path or EMBEDDINGS_PATH
    model = load_trained_model(checkpoint_path)
    data = dataset or BehavioralSequenceDataset.from_processed_file()
    bundle = extract_dataset_embeddings(model, data, batch_size=batch_size)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(bundle, destination)
    return destination
