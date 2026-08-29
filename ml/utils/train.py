"""Self-supervised training loop for the behavioral transformer."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from ml.models.transformer import (
    DIM_FEEDFORWARD,
    D_MODEL,
    DROPOUT,
    NHEAD,
    NUM_LAYERS,
    BehavioralTransformer,
)
from ml.utils.dataset import BehavioralSequenceDataset, make_dataloaders
from ml.utils.db import PROJECT_ROOT

CHECKPOINT_PATH = PROJECT_ROOT / "ml" / "models" / "neuroscope_msm.pt"


def _mean_msm_loss(
    model: BehavioralTransformer,
    loader: DataLoader[dict[str, Any]],
    optimizer: AdamW | None,
    max_grad_norm: float,
) -> dict[str, float]:
    train = optimizer is not None
    model.train(train)
    total_loss = 0.0
    total_action = 0.0
    total_reward = 0.0
    n_examples = 0

    for batch in loader:
        if optimizer is not None:
            optimizer.zero_grad(set_to_none=True)

        _hidden, loss, logs = model.masked_forward(
            batch["state"],
            batch["action"],
            batch["reward"],
            batch["delta_t"],
            batch["task_id"],
            batch["attention_mask"],
        )

        if optimizer is not None:
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            optimizer.step()

        batch_size = int(batch["action"].shape[0])
        total_loss += float(loss.detach()) * batch_size
        total_action += float(logs["loss_action"]) * batch_size
        total_reward += float(logs["loss_reward"]) * batch_size
        n_examples += batch_size

    denom = max(n_examples, 1)
    return {
        "loss": total_loss / denom,
        "loss_action": total_action / denom,
        "loss_reward": total_reward / denom,
        "n": float(n_examples),
    }


def save_checkpoint(
    model: BehavioralTransformer,
    spec: Mapping[str, Any],
    path: Path,
    epoch: int,
    metrics: Mapping[str, float],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "spec": dict(spec),
            "epoch": epoch,
            "metrics": dict(metrics),
            "config": {
                "d_model": D_MODEL,
                "nhead": NHEAD,
                "num_layers": NUM_LAYERS,
                "dim_feedforward": DIM_FEEDFORWARD,
                "dropout": DROPOUT,
            },
        },
        path,
    )
    return path


def run_training(
    *,
    epochs: int = 10,
    batch_size: int = 4,
    lr: float = 3e-4,
    weight_decay: float = 0.01,
    val_fraction: float = 0.2,
    seed: int = 42,
    max_grad_norm: float = 1.0,
    checkpoint_path: Path | None = None,
    dataset: BehavioralSequenceDataset | None = None,
) -> Path:
    """Train with AdamW + cosine decay; write weights to ml/models/."""
    torch.manual_seed(seed)
    destination = checkpoint_path or CHECKPOINT_PATH
    data = dataset or BehavioralSequenceDataset.from_processed_file()
    if len(data) == 0:
        raise RuntimeError(
            "No processed sequences found. Run `python main.py --extract` first."
        )

    train_loader, val_loader = make_dataloaders(
        data,
        batch_size=batch_size,
        val_fraction=val_fraction,
        seed=seed,
    )
    model = BehavioralTransformer.from_spec(data.spec)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=max(epochs, 1), eta_min=lr * 0.05)

    best_val = float("inf")
    last_metrics: dict[str, float] = {}

    print(f"[train] device={model.device} n={len(data)} epochs={epochs} batch_size={batch_size}")

    for epoch in range(1, epochs + 1):
        train_metrics = _mean_msm_loss(model, train_loader, optimizer, max_grad_norm)
        if len(val_loader.dataset) > 0:
            with torch.no_grad():
                val_metrics = _mean_msm_loss(model, val_loader, None, max_grad_norm)
        else:
            val_metrics = {"loss": train_metrics["loss"], "loss_action": 0.0, "loss_reward": 0.0, "n": 0.0}

        scheduler.step()
        lr_now = scheduler.get_last_lr()[0]
        last_metrics = {
            "train_loss": train_metrics["loss"],
            "train_loss_action": train_metrics["loss_action"],
            "train_loss_reward": train_metrics["loss_reward"],
            "val_loss": val_metrics["loss"],
            "val_loss_action": val_metrics["loss_action"],
            "val_loss_reward": val_metrics["loss_reward"],
            "lr": lr_now,
        }
        print(
            f"[train] epoch {epoch:03d}/{epochs} "
            f"train={train_metrics['loss']:.4f} "
            f"val={val_metrics['loss']:.4f} "
            f"lr={lr_now:.2e}"
        )

        if val_metrics["loss"] <= best_val:
            best_val = val_metrics["loss"]
            save_checkpoint(model, data.spec, destination, epoch, last_metrics)

    save_checkpoint(model, data.spec, destination, epochs, last_metrics)
    print(f"[train] saved weights to {destination}")
    return destination
