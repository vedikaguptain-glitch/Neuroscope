"""Unified timestep embeddings with absolute positional encoding."""

from __future__ import annotations

import math
from collections.abc import Mapping

import torch
from torch import nn

from ml.utils.preprocess import SEQUENCE_LENGTH, FeatureSpec


class AbsolutePositionalEncoding(nn.Module):
    """Sinusoidal absolute positions for the 240-trial sequence."""

    def __init__(self, d_model: int, max_len: int = SEQUENCE_LENGTH, dropout: float = 0.1) -> None:
        super().__init__()
        if d_model % 2 != 0:
            raise ValueError("d_model must be even so sine/cosine channels pair evenly.")
        self.dropout = nn.Dropout(dropout)

        position = torch.arange(max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model)
        )
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0), persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.size(1) > self.pe.size(1):
            raise ValueError(
                f"Sequence length {x.size(1)} exceeds positional encoding max_len {self.pe.size(1)}."
            )
        return self.dropout(x + self.pe[:, : x.size(1)])


class BehavioralEmbedding(nn.Module):
    """Maps [S_t, A_t, R_t, Δt] into one d_model vector per timestep."""

    def __init__(
        self,
        state_dim: int,
        action_vocab_size: int,
        reward_dim: int,
        d_model: int = 128,
        max_len: int = SEQUENCE_LENGTH,
        dropout: float = 0.1,
        task_vocab_size: int | None = None,
        padding_idx: int = 0,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.state_proj = nn.Linear(state_dim, d_model)
        self.action_emb = nn.Embedding(action_vocab_size, d_model, padding_idx=padding_idx)
        self.reward_proj = nn.Linear(reward_dim, d_model)
        self.rt_proj = nn.Linear(1, d_model)
        self.task_emb = (
            nn.Embedding(task_vocab_size, d_model, padding_idx=padding_idx)
            if task_vocab_size is not None
            else None
        )
        self.layer_norm = nn.LayerNorm(d_model)
        self.pos_enc = AbsolutePositionalEncoding(d_model, max_len=max_len, dropout=dropout)

    @classmethod
    def from_spec(
        cls,
        spec: FeatureSpec | Mapping[str, object],
        d_model: int = 128,
        dropout: float = 0.1,
    ) -> BehavioralEmbedding:
        state_dim = len(spec["numeric_state_keys"]) + len(spec["categorical_state_keys"])
        reward_dim = len(spec["numeric_reward_keys"]) + len(spec["categorical_reward_keys"])
        action_vocab = spec["action_vocab"]
        task_vocab = spec["task_vocab"]
        if not isinstance(action_vocab, dict) or not isinstance(task_vocab, dict):
            raise TypeError("Feature spec must include action_vocab and task_vocab mappings.")
        return cls(
            state_dim=state_dim,
            action_vocab_size=len(action_vocab),
            reward_dim=reward_dim,
            d_model=d_model,
            dropout=dropout,
            task_vocab_size=len(task_vocab),
        )

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        reward: torch.Tensor,
        delta_t: torch.Tensor,
        task_id: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if delta_t.dim() == 2:
            delta_t = delta_t.unsqueeze(-1)

        fused = (
            self.state_proj(state)
            + self.action_emb(action)
            + self.reward_proj(reward)
            + self.rt_proj(delta_t)
        )
        if self.task_emb is not None:
            if task_id is None:
                raise ValueError("task_id is required when the embedding includes a task table.")
            fused = fused + self.task_emb(task_id)

        return self.pos_enc(self.layer_norm(fused))
