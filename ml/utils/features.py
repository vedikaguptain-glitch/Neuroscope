"""Participant-local behavioral features and target definitions, independent of model search."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
import numpy as np
from ml.config import TASK_ORDER
from ml.utils.behavioral_models import mechanism_features

TARGET_ACTIONS = {"risk_pref": "gamble", "delay_disc": "delayed", "social_ultimatum": "accept"}


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except ValueError, TypeError:
        return None
    return result if np.isfinite(result) else None


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if len(values) else 0.0


def _slope(x: Sequence[float], y: Sequence[float]) -> float:
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(a) < 3 or np.std(a) < 1e-8:
        return 0.0
    a = a - a.mean()
    return float(a @ (b - b.mean()) / (a @ a))


def _summarize(features: dict[str, float], name: str, values: Sequence[float]) -> None:
    if not len(values):
        return
    x = np.asarray(values, dtype=float)
    features.update(
        {
            f"{name}.mean": float(x.mean()),
            f"{name}.std": float(x.std()),
            f"{name}.median": float(np.median(x)),
            f"{name}.iqr": float(np.quantile(x, 0.75) - np.quantile(x, 0.25)),
        }
    )


def behavior_features(
    session: Mapping[str, Any], held_out_task: str, *, include_mechanisms: bool = True
) -> dict[str, float]:
    """Use only the other tasks; never use demographics, IDs, dates or target trials."""
    features: dict[str, float] = {}
    for task in TASK_ORDER:
        if task == held_out_task:
            continue
        trials = sorted(
            (t for t in session.get("trials", []) if t.get("task_id") == task),
            key=lambda t: t["trial_index"],
        )
        n = len(trials)
        features[f"{task}.n_trials"] = float(n)
        if not n:
            continue
        if include_mechanisms:
            features.update(mechanism_features(trials, task))
        actions = [str(t.get("action_taken", "")) for t in trials]
        outcomes = [t.get("reward_received") or {} for t in trials]
        states = [t.get("state_vector") or {} for t in trials]
        log_rt = [float(np.log1p(max(_number(t.get("reaction_time_ms")) or 0, 0))) for t in trials]
        _summarize(features, f"{task}.log_rt", log_rt)
        features[f"{task}.rt_trend"] = _slope(np.linspace(0, 1, n), log_rt)
        features[f"{task}.rt_below_150ms"] = _mean([v < np.log1p(150) for v in log_rt])
        features[f"{task}.rt_above_30s"] = _mean([v > np.log1p(30000) for v in log_rt])
        counts = Counter(actions)
        features[f"{task}.action_entropy"] = -sum((c / n) * np.log(c / n) for c in counts.values())
        features[f"{task}.repeat_rate"] = _mean([a == b for a, b in zip(actions, actions[1:])])
        for action in (
            "A",
            "B",
            "0",
            "1",
            "2",
            "3",
            "safe",
            "gamble",
            "immediate",
            "delayed",
            "accept",
            "reject",
        ):
            selected = [float(a == action) for a in actions]
            features[f"{task}.action.{action}"] = _mean(selected)
            features[f"{task}.action.{action}.change"] = _mean(selected[-max(n // 3, 1) :]) - _mean(
                selected[: max(n // 3, 1)]
            )
        correct = [float(o.get("outcome") in ("correct", "reward", "win")) for o in outcomes]
        for i, indices in enumerate(np.array_split(np.arange(n), 3)):
            features[f"{task}.block{i}.positive_feedback"] = _mean([correct[j] for j in indices])
            features[f"{task}.block{i}.log_rt"] = _mean([log_rt[j] for j in indices])
        for positive in (0, 1):
            eligible = [i for i in range(n - 1) if correct[i] == positive]
            features[f"{task}.repeat_after_feedback{positive}"] = _mean(
                [actions[i + 1] == actions[i] for i in eligible]
            )
        if task == "delay_disc":
            chosen = [float(a == "delayed") for a in actions]
            delays = [np.log1p(max(_number(s.get("delay_duration")) or 0, 0)) for s in states]
            gains = [
                (_number(s.get("delayed_reward")) or 0) - (_number(s.get("immediate_reward")) or 0)
                for s in states
            ]
            features[f"{task}.delay_sensitivity"] = _slope(delays, chosen)
            features[f"{task}.gain_sensitivity"] = _slope(gains, chosen)
        if task == "risk_pref":
            chosen = [float(a == "gamble") for a in actions]
            advantage = [
                (_number(s.get("gamble_probability")) or 0)
                * (_number(s.get("gamble_win_amount")) or 0)
                - (_number(s.get("safe_amount")) or 0)
                for s in states
            ]
            features[f"{task}.ev_sensitivity"] = _slope(advantage, chosen)
            for favorable in (False, True):
                features[f"{task}.gamble_when_favorable{favorable}"] = _mean(
                    [a for a, ev in zip(chosen, advantage) if (ev > 0) == favorable]
                )
        if task == "rule_discovery":
            for rule in ("color", "shape", "number"):
                match = [
                    float(a == str(s.get(f"{rule}_match_index"))) for a, s in zip(actions, states)
                ]
                features[f"{task}.{rule}_match_rate"] = _mean(match)
                features[f"{task}.{rule}_after_error"] = _mean(
                    [match[i] for i in range(1, n) if not correct[i - 1]]
                )
        if task == "social_ultimatum":
            offers = [v for a in actions if (v := _number(a)) is not None]
            _summarize(features, f"{task}.offer", offers)
            responses = [i for i, a in enumerate(actions) if a in ("accept", "reject")]
            accepted = [float(actions[i] == "accept") for i in responses]
            partner_offers = [_number(states[i].get("partner_offer")) or 0 for i in responses]
            features[f"{task}.responder_accept_rate"] = _mean(accepted)
            features[f"{task}.offer_sensitivity"] = _slope(partner_offers, accepted)
            features[f"{task}.accept_low_offer"] = _mean(
                [a for a, offer in zip(accepted, partner_offers) if offer < 30]
            )
    return features


def target_label(session: Mapping[str, Any], held_out_task: str) -> int:
    if held_out_task not in TARGET_ACTIONS:
        raise RuntimeError("Optimization supports risk_pref, delay_disc and social_ultimatum.")
    actions = [
        t.get("action_taken")
        for t in session.get("trials", [])
        if t.get("task_id") == held_out_task
    ]
    if held_out_task == "social_ultimatum":
        actions = [a for a in actions if a in ("accept", "reject")]
    if not actions:
        raise RuntimeError(f"A session has no valid {held_out_task} responses.")
    # Integer comparison avoids a float32 boundary error at exactly 50%.
    return int(2 * sum(a == TARGET_ACTIONS[held_out_task] for a in actions) >= len(actions))
