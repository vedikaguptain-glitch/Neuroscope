"""Regularized, participant-local choice-policy estimates and feature views.

Coefficients summarize behavior conditional on recorded task conditions. They are
exploratory predictive features, not established psychological traits or causal effects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.base import BaseEstimator, TransformerMixin


class FeatureView(TransformerMixin, BaseEstimator):
    """Select a fixed feature family/task without learning from evaluation records."""

    def __init__(self, mode: str = "summary", task: str | None = None):
        self.mode = mode
        self.task = task

    def fit(self, X, y=None):
        if self.mode not in ("summary", "mechanism", "all"):
            raise ValueError("Unknown feature view.")
        self.fitted_ = True
        return self

    def transform(self, X):
        output = []
        for row in X:
            selected = {
                key: value
                for key, value in row.items()
                if (self.task is None or key.startswith(self.task + "."))
                and (self.mode == "all" or (".mechanism." in key) == (self.mode == "mechanism"))
            }
            output.append(selected or {"__empty__": 0.0})
        return output


def fit_choice_weights(
    design: np.ndarray, choices: np.ndarray, precision: float = 1.0
) -> np.ndarray:
    """Gaussian-prior MAP logistic coefficients, including a penalized intercept.

    Inputs must already use meaningful, comparable units. A fixed shared zero-centered
    prior prevents separation or constant choices from producing infinite coefficients.
    No information from other participants or the prediction target is used here.
    """
    x, y = np.asarray(design, dtype=float), np.asarray(choices, dtype=float)
    if x.ndim != 2 or y.shape != (len(x),) or not len(y):
        raise ValueError("Expected a nonempty [trials, features] design and binary choices.")
    if (
        not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or not np.isin(y, [0.0, 1.0]).all()
        or precision <= 0
    ):
        raise ValueError(
            "Choice fitting requires finite inputs, binary outcomes and a positive prior precision."
        )
    x = np.column_stack([np.ones(len(x)), x])

    def objective(weights):
        logits = x @ weights
        loss = np.logaddexp(0, logits).sum() - y @ logits + 0.5 * precision * (weights @ weights)
        gradient = x.T @ (expit(logits) - y) + precision * weights
        return float(loss), gradient

    fit = minimize(
        objective,
        np.zeros(x.shape[1]),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 300, "ftol": 1e-10},
    )
    if not fit.success or not np.isfinite(fit.x).all():
        raise RuntimeError(f"Behavioral policy fitting failed: {fit.message}")
    return fit.x


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if np.isfinite(number) else default
    except ValueError, TypeError:
        return default


def _average(values: Sequence[float]) -> float:
    return float(np.mean(values)) if len(values) else 0.0


def _policy(features, task, names, design, choices):
    if not len(choices):
        return
    coefficients = fit_choice_weights(np.asarray(design), np.asarray(choices))
    for name, coefficient in zip(["intercept"] + names, coefficients):
        features[f"{task}.mechanism.{name}"] = float(coefficient)
    features[f"{task}.mechanism.n_policy_trials"] = float(len(choices))


def mechanism_features(trials: Sequence[Mapping[str, Any]], task: str) -> dict[str, float]:
    """Estimate condition sensitivity, history effects and position preferences."""
    features: dict[str, float] = {}
    n = len(trials)
    if not n:
        return features
    states = [t.get("state_vector") or {} for t in trials]
    actions = [str(t.get("action_taken", "")) for t in trials]
    outcomes = [t.get("reward_received") or {} for t in trials]
    time = np.linspace(-1, 1, n)
    if task in ("delay_disc", "risk_pref"):
        positive = "delayed" if task == "delay_disc" else "gamble"
        chosen = np.array([float(a == positive) for a in actions])
        previous = np.r_[0.0, 2 * chosen[:-1] - 1]
        if task == "delay_disc":
            design = [
                [
                    (_float(s.get("delayed_reward")) - _float(s.get("immediate_reward"))) / 100,
                    np.log1p(max(_float(s.get("delay_duration")), 0)) / np.log(91),
                    previous[i],
                    time[i],
                ]
                for i, s in enumerate(states)
            ]
            _policy(
                features,
                task,
                ["reward_advantage", "delay_cost", "previous_choice", "time_drift"],
                design,
                chosen,
            )
        else:
            design = [
                [
                    (
                        _float(s.get("gamble_probability")) * _float(s.get("gamble_win_amount"))
                        - _float(s.get("safe_amount"))
                    )
                    / 100,
                    _float(s.get("gamble_probability")) - 0.5,
                    previous[i],
                    float(s.get("safe_side") == "left") - 0.5,
                ]
                for i, s in enumerate(states)
            ]
            _policy(
                features,
                task,
                ["expected_value", "probability", "previous_choice", "safe_on_left"],
                design,
                chosen,
            )
    elif task == "prob_learning":
        chosen = np.array([float(a == "A") for a in actions])
        # Fixed recency learner supplies a past-feedback value contrast; alpha=.2
        # is a feature construction rule, not an estimated participant learning rate.
        q = np.array([0.5, 0.5])
        design = []
        for i, (a, s, outcome) in enumerate(zip(actions, states, outcomes)):
            prev = (2 * chosen[i - 1] - 1) if i else 0.0
            feedback = (2 * float(_float(outcomes[i - 1].get("points")) > 0) - 1) if i else 0.0
            design.append(
                [q[0] - q[1], prev, prev * feedback, float(s.get("left_symbol") == "A") - 0.5]
            )
            index = 0 if a == "A" else 1
            q[index] += 0.2 * (float(_float(outcome.get("points")) > 0) - q[index])
        _policy(
            features,
            task,
            ["recent_value", "previous_choice", "feedback_x_previous_choice", "A_on_left"],
            design,
            chosen,
        )
        midpoint = n // 2
        features[f"{task}.mechanism.reversal_adaptation"] = _average(chosen[:midpoint]) - _average(
            chosen[midpoint:]
        )
    elif task == "social_ultimatum":
        positions = [i for i, a in enumerate(actions) if a in ("accept", "reject")]
        chosen = [float(actions[i] == "accept") for i in positions]
        design = [
            [
                _float(states[i].get("partner_offer"))
                / max(_float(states[i].get("endowment"), 100), 1)
                - 0.5,
                (2 * chosen[j - 1] - 1) if j else 0.0,
                time[i],
            ]
            for j, i in enumerate(positions)
        ]
        _policy(features, task, ["offer_fraction", "previous_choice", "time_drift"], design, chosen)
        proposer = [i for i, a in enumerate(actions) if a not in ("accept", "reject")]
        offers = [
            _float(actions[i]) / max(_float(states[i].get("endowment"), 100), 1) for i in proposer
        ]
        features[f"{task}.mechanism.offer_fraction_mean"] = _average(offers)
        features[f"{task}.mechanism.offer_fraction_sd"] = float(np.std(offers)) if offers else 0.0
        for accepted in (True, False):
            changes = [
                offers[j] - offers[j - 1]
                for j in range(1, len(proposer))
                if bool(outcomes[proposer[j - 1]].get("accepted")) == accepted
            ]
            features[f"{task}.mechanism.offer_change_after_accepted{accepted}"] = _average(changes)
    elif task == "rule_discovery":
        rules = ("color", "shape", "number")
        selected_rules = []
        for action, state in zip(actions, states):
            selected_rules.append(
                next(
                    (
                        r
                        for r in rules
                        if _float(action, -1) == _float(state.get(f"{r}_match_index"), -2)
                    ),
                    "none",
                )
            )
        correct = [float(o.get("outcome") == "correct") for o in outcomes]
        for feedback in (0, 1):
            indices = [i for i in range(1, n) if correct[i - 1] == feedback]
            features[f"{task}.mechanism.rule_repeat_after_correct{feedback}"] = _average(
                [selected_rules[i] == selected_rules[i - 1] for i in indices]
            )
        features[f"{task}.mechanism.unmatched_choice_rate"] = _average(
            [r == "none" for r in selected_rules]
        )
        # The collection protocol uses four rule blocks, color/shape/number/color.
        for block, indices in enumerate(np.array_split(np.arange(n), 4)):
            features[f"{task}.mechanism.block{block}_accuracy"] = _average(
                [correct[i] for i in indices]
            )
            features[f"{task}.mechanism.block{block}_adaptation"] = _average(
                [correct[i] for i in indices[-3:]]
            ) - _average([correct[i] for i in indices[:3]])
    return features
