"""Transformer encoder for sequential decision-making representations."""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn

from ml.models.embeddings import BehavioralEmbedding
from ml.utils.msm import MSMHeads, apply_msm_mask, msm_loss
from ml.utils.preprocess import FeatureSpec

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Sized for 240-step behavioral sequences on a typical CPU, with GPU if present.
D_MODEL = 128
NHEAD = 4
NUM_LAYERS = 4
DIM_FEEDFORWARD = 256
DROPOUT = 0.1


class BehavioralTransformer(nn.Module):
    """Encoder-only transformer over fused [S_t, A_t, R_t, Δt] embeddings."""

    def __init__(
        self,
        embedding: BehavioralEmbedding,
        d_model: int = D_MODEL,
        nhead: int = NHEAD,
        num_layers: int = NUM_LAYERS,
        dim_feedforward: int = DIM_FEEDFORWARD,
        dropout: float = DROPOUT,
        action_vocab_size: int = 2,
        reward_dim: int = 1,
        device: torch.device | None = None,
    ) -> None:
        super().__init__()
        if d_model % nhead != 0:
            raise ValueError("d_model must be divisible by nhead.")
        self.d_model = d_model
        self.embedding = embedding
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers,
            enable_nested_tensor=False,
        )
        self.final_norm = nn.LayerNorm(d_model)
        self.msm_heads = MSMHeads(d_model, action_vocab_size, reward_dim)
        resolved = device if device is not None else DEVICE
        self.to(resolved)

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    @classmethod
    def from_spec(
        cls,
        spec: FeatureSpec | Mapping[str, object],
        d_model: int = D_MODEL,
        nhead: int = NHEAD,
        num_layers: int = NUM_LAYERS,
        dim_feedforward: int = DIM_FEEDFORWARD,
        dropout: float = DROPOUT,
        device: torch.device | None = None,
    ) -> BehavioralTransformer:
        embedding = BehavioralEmbedding.from_spec(spec, d_model=d_model, dropout=dropout)
        action_vocab = spec["action_vocab"]
        if not isinstance(action_vocab, dict):
            raise TypeError("Feature spec must include action_vocab.")
        reward_dim = len(spec["numeric_reward_keys"]) + len(spec["categorical_reward_keys"])
        return cls(
            embedding=embedding,
            d_model=d_model,
            nhead=nhead,
            num_layers=num_layers,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            action_vocab_size=len(action_vocab),
            reward_dim=max(reward_dim, 1),
            device=device,
        )

    def _move(self, tensor: torch.Tensor) -> torch.Tensor:
        return tensor.to(self.device, non_blocking=self.device.type == "cuda")

    def encode(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        reward: torch.Tensor,
        delta_t: torch.Tensor,
        task_id: torch.Tensor | None = None,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        state = self._move(state)
        action = self._move(action)
        reward = self._move(reward)
        delta_t = self._move(delta_t)
        task = self._move(task_id) if task_id is not None else None

        hidden = self.embedding(state, action, reward, delta_t, task)
        key_padding_mask = None
        if attention_mask is not None:
            mask = self._move(attention_mask)
            key_padding_mask = mask == 0
        encoded = self.encoder(hidden, src_key_padding_mask=key_padding_mask)
        return self.final_norm(encoded)

    def masked_forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        reward: torch.Tensor,
        delta_t: torch.Tensor,
        task_id: torch.Tensor | None = None,
        attention_mask: torch.Tensor | None = None,
        mask_prob: float = 0.15,
        generator: torch.Generator | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        """Run MSM: corrupt actions or rewards, then predict the hidden values."""
        if attention_mask is None:
            attention_mask = torch.ones_like(action, dtype=torch.long)

        action = self._move(action)
        reward = self._move(reward)
        attention_mask = self._move(attention_mask)
        corruption = apply_msm_mask(
            action,
            reward,
            attention_mask,
            mask_prob=mask_prob,
            generator=generator,
        )
        hidden = self.encode(
            state,
            corruption.action_input,
            corruption.reward_input,
            delta_t,
            task_id=task_id,
            attention_mask=attention_mask,
        )
        action_logits, reward_pred = self.msm_heads(hidden)
        loss, logs = msm_loss(
            action_logits,
            reward_pred,
            action,
            reward,
            corruption.action_mask,
            corruption.reward_mask,
        )
        return hidden, loss, logs

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        reward: torch.Tensor,
        delta_t: torch.Tensor,
        task_id: torch.Tensor | None = None,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        return self.encode(
            state,
            action,
            reward,
            delta_t,
            task_id=task_id,
            attention_mask=attention_mask,
        )
