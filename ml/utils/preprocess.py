"""Parse raw sessions into x_t = [S_t, A_t, R_t, Δt] tensors."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict, cast

import numpy as np
import torch

from ml.utils.db import PROJECT_ROOT
from ml.utils.extract import RAW_PARTICIPANTS_PATH

SEQUENCE_LENGTH = 240
PAD_TOKEN = "<pad>"
UNK_TOKEN = "<unk>"
TASK_ORDER = (
    "prob_learning",
    "risk_pref",
    "delay_disc",
    "rule_discovery",
    "social_ultimatum",
)

PROCESSED_PATH = PROJECT_ROOT / "ml" / "data" / "processed.pt"
VOCAB_PATH = PROJECT_ROOT / "ml" / "data" / "vocab.json"


class Vocab:
    def __init__(self, tokens: Sequence[str]) -> None:
        ordered = [PAD_TOKEN, UNK_TOKEN]
        for token in tokens:
            if token not in ordered:
                ordered.append(token)
        self.token_to_id = {token: index for index, token in enumerate(ordered)}
        self.id_to_token = {index: token for token, index in self.token_to_id.items()}

    def encode(self, token: str | None) -> int:
        if token is None:
            return self.token_to_id[PAD_TOKEN]
        return self.token_to_id.get(token, self.token_to_id[UNK_TOKEN])

    def to_dict(self) -> dict[str, int]:
        return dict(self.token_to_id)

    @classmethod
    def from_dict(cls, mapping: Mapping[str, int]) -> Vocab:
        tokens = [
            token
            for token, _ in sorted(mapping.items(), key=lambda item: item[1])
            if token not in {PAD_TOKEN, UNK_TOKEN}
        ]
        return cls(tokens)


class FeatureSpec(TypedDict):
    numeric_state_keys: list[str]
    categorical_state_keys: list[str]
    numeric_reward_keys: list[str]
    categorical_reward_keys: list[str]
    rt_log_mean: float
    rt_log_std: float
    action_vocab: dict[str, int]
    task_vocab: dict[str, int]
    state_cat_vocabs: dict[str, dict[str, int]]
    reward_cat_vocabs: dict[str, dict[str, int]]


def load_raw_participants(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or RAW_PARTICIPANTS_PATH
    if not source.exists():
        raise RuntimeError(
            f"Raw data not found at {source}. Run `python main.py --extract` first."
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("raw_participants.json must contain a JSON array.")
    return payload


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _leaf_items(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, Mapping):
        items: list[tuple[str, Any]] = []
        for key, child in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            items.extend(_leaf_items(child, next_prefix))
        return items
    if isinstance(value, list):
        items = []
        for index, child in enumerate(value):
            items.extend(_leaf_items(child, f"{prefix}[{index}]"))
        return items
    return [(prefix, value)] if prefix else []


def _numeric_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return float(value) if isinstance(value, bool) else None
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        if np.isnan(number) or np.isinf(number):
            return None
        return number
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        if np.isnan(number) or np.isinf(number):
            return None
        return number
    return None


def _split_leaves(blob: Any) -> tuple[dict[str, float], dict[str, str]]:
    numeric: dict[str, float] = {}
    categorical: dict[str, str] = {}
    for key, value in _leaf_items(blob):
        as_number = _numeric_value(value)
        if as_number is not None:
            numeric[key] = as_number
        elif isinstance(value, str) and value != "":
            categorical[key] = value
    return numeric, categorical


def _collect_keys_and_values(
    sessions: Sequence[Mapping[str, Any]],
) -> tuple[
    set[str],
    set[str],
    set[str],
    set[str],
    dict[str, set[str]],
    dict[str, set[str]],
    set[str],
    list[float],
]:
    numeric_state_keys: set[str] = set()
    categorical_state_keys: set[str] = set()
    numeric_reward_keys: set[str] = set()
    categorical_reward_keys: set[str] = set()
    state_cat_values: dict[str, set[str]] = {}
    reward_cat_values: dict[str, set[str]] = {}
    actions: set[str] = set()
    log_rts: list[float] = []

    for session in sessions:
        for trial in session.get("trials") or []:
            if not isinstance(trial, Mapping):
                continue
            action = trial.get("action_taken")
            if isinstance(action, str) and action:
                actions.add(action)

            rt = _numeric_value(trial.get("reaction_time_ms"))
            if rt is not None and rt >= 0:
                log_rts.append(float(np.log1p(rt)))

            state_num, state_cat = _split_leaves(trial.get("state_vector"))
            reward_num, reward_cat = _split_leaves(trial.get("reward_received"))
            numeric_state_keys.update(state_num)
            numeric_reward_keys.update(reward_num)
            categorical_state_keys.update(state_cat)
            categorical_reward_keys.update(reward_cat)
            for key, value in state_cat.items():
                state_cat_values.setdefault(key, set()).add(value)
            for key, value in reward_cat.items():
                reward_cat_values.setdefault(key, set()).add(value)

    return (
        numeric_state_keys,
        categorical_state_keys,
        numeric_reward_keys,
        categorical_reward_keys,
        state_cat_values,
        reward_cat_values,
        actions,
        log_rts,
    )


def fit_feature_spec(sessions: Sequence[Mapping[str, Any]]) -> FeatureSpec:
    (
        numeric_state_keys,
        categorical_state_keys,
        numeric_reward_keys,
        categorical_reward_keys,
        state_cat_values,
        reward_cat_values,
        actions,
        log_rts,
    ) = _collect_keys_and_values(sessions)

    rt_mean = float(np.mean(log_rts)) if log_rts else 0.0
    rt_std = float(np.std(log_rts)) if log_rts else 1.0
    if rt_std < 1e-8:
        rt_std = 1.0

    return FeatureSpec(
        numeric_state_keys=sorted(numeric_state_keys),
        categorical_state_keys=sorted(categorical_state_keys),
        numeric_reward_keys=sorted(numeric_reward_keys),
        categorical_reward_keys=sorted(categorical_reward_keys),
        rt_log_mean=rt_mean,
        rt_log_std=rt_std,
        action_vocab=Vocab(sorted(actions)).to_dict(),
        task_vocab=Vocab(TASK_ORDER).to_dict(),
        state_cat_vocabs={
            key: Vocab(sorted(values)).to_dict()
            for key, values in sorted(state_cat_values.items())
        },
        reward_cat_vocabs={
            key: Vocab(sorted(values)).to_dict()
            for key, values in sorted(reward_cat_values.items())
        },
    )


def _vectorize(
    numeric: Mapping[str, float],
    categorical: Mapping[str, str],
    numeric_keys: Sequence[str],
    categorical_keys: Sequence[str],
    cat_vocabs: Mapping[str, Vocab],
) -> list[float]:
    values = [float(numeric.get(key, 0.0)) for key in numeric_keys]
    for key in categorical_keys:
        vocab = cat_vocabs.get(key)
        token = categorical.get(key)
        values.append(float(vocab.encode(token) if vocab is not None else 0))
    return values


def normalize_reaction_time(rt_ms: Any, spec: FeatureSpec) -> float:
    rt = _numeric_value(rt_ms)
    if rt is None or rt < 0:
        rt = 0.0
    log_rt = float(np.log1p(rt))
    return (log_rt - spec["rt_log_mean"]) / spec["rt_log_std"]


def trial_to_xt(
    trial: Mapping[str, Any],
    spec: FeatureSpec,
    action_vocab: Vocab,
    task_vocab: Vocab,
    state_cat_vocabs: Mapping[str, Vocab],
    reward_cat_vocabs: Mapping[str, Vocab],
) -> tuple[list[float], int, list[float], float, int]:
    state_num, state_cat = _split_leaves(trial.get("state_vector"))
    reward_num, reward_cat = _split_leaves(trial.get("reward_received"))
    state = _vectorize(
        state_num,
        state_cat,
        spec["numeric_state_keys"],
        spec["categorical_state_keys"],
        state_cat_vocabs,
    )
    reward = _vectorize(
        reward_num,
        reward_cat,
        spec["numeric_reward_keys"],
        spec["categorical_reward_keys"],
        reward_cat_vocabs,
    )
    action_id = action_vocab.encode(
        trial.get("action_taken") if isinstance(trial.get("action_taken"), str) else None
    )
    task_id = task_vocab.encode(
        trial.get("task_id") if isinstance(trial.get("task_id"), str) else None
    )
    delta_t = normalize_reaction_time(trial.get("reaction_time_ms"), spec)
    return state, action_id, reward, delta_t, task_id


def _pad_or_trim(values: list[Any], fill: Any) -> list[Any]:
    if len(values) >= SEQUENCE_LENGTH:
        return values[:SEQUENCE_LENGTH]
    return values + [fill] * (SEQUENCE_LENGTH - len(values))


def session_to_tensors(
    session: Mapping[str, Any],
    spec: FeatureSpec,
) -> dict[str, torch.Tensor]:
    action_vocab = Vocab.from_dict(spec["action_vocab"])
    task_vocab = Vocab.from_dict(spec["task_vocab"])
    state_cat_vocabs = {
        key: Vocab.from_dict(mapping) for key, mapping in spec["state_cat_vocabs"].items()
    }
    reward_cat_vocabs = {
        key: Vocab.from_dict(mapping) for key, mapping in spec["reward_cat_vocabs"].items()
    }
    trials = [trial for trial in (session.get("trials") or []) if isinstance(trial, Mapping)]
    encoded = [
        trial_to_xt(
            trial,
            spec,
            action_vocab,
            task_vocab,
            state_cat_vocabs,
            reward_cat_vocabs,
        )
        for trial in trials
    ]

    state_dim = len(spec["numeric_state_keys"]) + len(spec["categorical_state_keys"])
    reward_dim = len(spec["numeric_reward_keys"]) + len(spec["categorical_reward_keys"])
    zero_state = [0.0] * state_dim
    zero_reward = [0.0] * reward_dim
    pad_action = action_vocab.encode(None)
    pad_task = task_vocab.encode(None)

    if not encoded:
        states = [zero_state] * SEQUENCE_LENGTH
        actions = [pad_action] * SEQUENCE_LENGTH
        rewards = [zero_reward] * SEQUENCE_LENGTH
        deltas = [0.0] * SEQUENCE_LENGTH
        tasks = [pad_task] * SEQUENCE_LENGTH
    else:
        states = _pad_or_trim([row[0] for row in encoded], zero_state)
        actions = _pad_or_trim([row[1] for row in encoded], pad_action)
        rewards = _pad_or_trim([row[2] for row in encoded], zero_reward)
        deltas = _pad_or_trim([row[3] for row in encoded], 0.0)
        tasks = _pad_or_trim([row[4] for row in encoded], pad_task)

    state_tensor = torch.tensor(states, dtype=torch.float32)
    action_tensor = torch.tensor(actions, dtype=torch.long)
    reward_tensor = torch.tensor(rewards, dtype=torch.float32)
    delta_tensor = torch.tensor(deltas, dtype=torch.float32).unsqueeze(-1)
    task_tensor = torch.tensor(tasks, dtype=torch.long)
    x_t = torch.cat(
        [state_tensor, action_tensor.unsqueeze(-1).float(), reward_tensor, delta_tensor],
        dim=-1,
    )
    return {
        "state": state_tensor,
        "action": action_tensor,
        "reward": reward_tensor,
        "delta_t": delta_tensor,
        "task_id": task_tensor,
        "x": x_t,
    }


def preprocess_sessions(
    sessions: Sequence[Mapping[str, Any]],
    spec: FeatureSpec | None = None,
) -> dict[str, Any]:
    fitted = spec or fit_feature_spec(sessions)
    participant_ids: list[str] = []
    packed: dict[str, list[torch.Tensor]] = {
        "state": [],
        "action": [],
        "reward": [],
        "delta_t": [],
        "task_id": [],
        "x": [],
    }
    for session in sessions:
        participant_id = session.get("participant_id")
        participant_ids.append(str(participant_id) if participant_id is not None else "")
        tensors = session_to_tensors(session, fitted)
        for key, tensor in tensors.items():
            packed[key].append(tensor)

    stacked = {
        key: torch.stack(values) if values else torch.empty(0)
        for key, values in packed.items()
    }
    stacked["participant_ids"] = participant_ids
    stacked["spec"] = fitted
    return stacked


def save_preprocessor_artifacts(bundle: Mapping[str, Any]) -> tuple[Path, Path]:
    spec = cast(FeatureSpec, bundle["spec"])
    VOCAB_PATH.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    torch.save(
        {
            "participant_ids": bundle["participant_ids"],
            "state": bundle["state"],
            "action": bundle["action"],
            "reward": bundle["reward"],
            "delta_t": bundle["delta_t"],
            "task_id": bundle["task_id"],
            "x": bundle["x"],
        },
        PROCESSED_PATH,
    )
    return PROCESSED_PATH, VOCAB_PATH


def preprocess_raw_participants(raw_path: Path | None = None) -> dict[str, Any]:
    sessions = load_raw_participants(raw_path)
    bundle = preprocess_sessions(sessions)
    save_preprocessor_artifacts(bundle)
    return bundle
