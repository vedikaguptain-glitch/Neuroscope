"""Masked sequence modeling (MSM) for actions and rewards."""

from __future__ import annotations

from typing import NamedTuple

import torch
from torch import nn
from torch.nn import functional as F

MASK_PROB = 0.15
ACTION_MASK_PROB = 0.5
PAD_ACTION_ID = 0


class MSMCorruption(NamedTuple):
    action_input: torch.Tensor
    reward_input: torch.Tensor
    action_mask: torch.Tensor
    reward_mask: torch.Tensor


def apply_msm_mask(
    action: torch.Tensor,
    reward: torch.Tensor,
    attention_mask: torch.Tensor,
    mask_prob: float = MASK_PROB,
    action_mask_prob: float = ACTION_MASK_PROB,
    pad_action_id: int = PAD_ACTION_ID,
    generator: torch.Generator | None = None,
) -> MSMCorruption:
    """Randomly hide action_taken or reward_received at valid timesteps.

    Selected positions keep their state and reaction time so the encoder can
    still attend to that trial. Real padding stays padding and is never masked.
    """
    if action.shape[:2] != reward.shape[:2] or action.shape[:2] != attention_mask.shape[:2]:
        raise ValueError("action, reward, and attention_mask must share [batch, time] shape.")

    valid = attention_mask.bool()
    rand_device = action.device
    select = torch.rand(action.shape, device=rand_device, generator=generator) < mask_prob
    candidate = valid & select

    # If a sequence has valid trials but none were sampled, mask one trial.
    missing = valid.any(dim=1) & ~candidate.any(dim=1)
    if missing.any():
        valid_f = valid.float().masked_fill(~valid, 0.0)
        sampled = torch.multinomial(valid_f[missing], num_samples=1).squeeze(-1)
        candidate[missing, sampled] = True

    choose_action = (
        torch.rand(action.shape, device=rand_device, generator=generator) < action_mask_prob
    )
    action_mask = candidate & choose_action
    reward_mask = candidate & ~choose_action

    action_input = action.clone()
    reward_input = reward.clone()
    action_input[action_mask] = pad_action_id
    reward_input[reward_mask] = 0
    return MSMCorruption(action_input, reward_input, action_mask, reward_mask)


def msm_loss(
    action_logits: torch.Tensor,
    reward_pred: torch.Tensor,
    action_target: torch.Tensor,
    reward_target: torch.Tensor,
    action_mask: torch.Tensor,
    reward_mask: torch.Tensor,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Predict masked actions (cross-entropy) and masked rewards (MSE)."""
    loss = action_logits.new_zeros(())
    logs: dict[str, torch.Tensor] = {
        "loss_action": action_logits.new_zeros(()),
        "loss_reward": action_logits.new_zeros(()),
        "n_action_masked": action_mask.sum().to(action_logits.dtype),
        "n_reward_masked": reward_mask.sum().to(action_logits.dtype),
    }

    if action_mask.any():
        vocab = action_logits.size(-1)
        targets = action_target.masked_fill(~action_mask, -100)
        loss_action = F.cross_entropy(
            action_logits.reshape(-1, vocab),
            targets.reshape(-1),
            ignore_index=-100,
        )
        loss = loss + loss_action
        logs["loss_action"] = loss_action.detach()

    if reward_mask.any():
        loss_reward = F.mse_loss(reward_pred[reward_mask], reward_target[reward_mask])
        loss = loss + loss_reward
        logs["loss_reward"] = loss_reward.detach()

    logs["loss"] = loss.detach()
    return loss, logs


class MSMHeads(nn.Module):
    """Decode encoder states back to action classes and reward vectors."""

    def __init__(self, d_model: int, action_vocab_size: int, reward_dim: int) -> None:
        super().__init__()
        self.action_head = nn.Linear(d_model, action_vocab_size)
        self.reward_head = nn.Linear(d_model, reward_dim)

    def forward(self, hidden: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.action_head(hidden), self.reward_head(hidden)
