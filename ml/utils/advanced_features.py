"""Richer participant-local representations; target-task trials are excluded first."""

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

from ml.config import TASK_ORDER
from ml.utils.features import behavior_features, _number


def _float(value):
    return _number(value) or 0.0


def _mean(values):
    return float(np.mean(values)) if len(values) else 0.0


def _semantic_action(trial):
    action = str(trial["action_taken"])
    if trial["task_id"] == "rule_discovery":
        state = trial["state_vector"]
        return next(
            (
                rule
                for rule in ("color", "shape", "number")
                if str(state.get(f"{rule}_match_index")) == action
            ),
            "none",
        )
    return action


def advanced_features(session, held_out_task="risk_pref"):
    features = behavior_features(session, held_out_task)
    eligible = [t for t in session["trials"] if t["task_id"] != held_out_task]
    all_rt = np.array([np.log1p(t["reaction_time_ms"]) for t in eligible])
    overall_median = float(np.median(all_rt)) if len(all_rt) else 0.0
    for task in TASK_ORDER:
        if task == held_out_task:
            continue
        trials = sorted(
            [t for t in eligible if t["task_id"] == task], key=lambda t: t["trial_index"]
        )
        n = len(trials)
        if not n:
            continue
        actions = [_semantic_action(t) for t in trials]
        rt = np.array([np.log1p(t["reaction_time_ms"]) for t in trials])
        rewards = [t["reward_received"] for t in trials]
        positive = [float(o.get("outcome") in ("correct", "reward", "win")) for o in rewards]
        prefix = f"{task}.advanced."
        features[prefix + "relative_log_rt"] = float(np.median(rt)) - overall_median
        features[prefix + "rt_mad"] = float(np.median(np.abs(rt - np.median(rt))))
        features[prefix + "rt_lag1"] = (
            float(np.corrcoef(rt[:-1], rt[1:])[0, 1])
            if n > 3 and np.std(rt[:-1]) > 1e-8 and np.std(rt[1:]) > 1e-8
            else 0.0
        )
        features[prefix + "same_semantic_action"] = _mean(
            [a == b for a, b in zip(actions, actions[1:])]
        )
        for rewarded in (0, 1):
            indices = [i for i in range(1, n) if positive[i - 1] == rewarded]
            features[prefix + f"semantic_stay_after{rewarded}"] = _mean(
                [actions[i] == actions[i - 1] for i in indices]
            )
        # Fixed windows preserve reversal/adaptation information lost by global pooling.
        for width in (5, 10):
            for start in range(0, n, width):
                block = trials[start : start + width]
                block_actions = actions[start : start + width]
                name = prefix + f"window{width}.{start // width}."
                features[name + "log_rt_mean"] = float(np.mean(rt[start : start + width]))
                features[name + "log_rt_sd"] = float(np.std(rt[start : start + width]))
                features[name + "positive_feedback"] = _mean(positive[start : start + width])
                for action in (
                    "A",
                    "B",
                    "immediate",
                    "delayed",
                    "color",
                    "shape",
                    "number",
                    "none",
                    "accept",
                    "reject",
                ):
                    features[name + action] = _mean([a == action for a in block_actions])
                offers = [
                    float(t["action_taken"]) / 100
                    for t in block
                    if t["task_id"] == "social_ultimatum"
                    and str(t["action_taken"]).replace(".", "", 1).isdigit()
                ]
                if offers:
                    features[name + "offer_mean"] = _mean(offers)
        for i, trial in enumerate(trials):
            name = f"{task}.sequence.{trial['trial_index']}."
            features[name + "log_rt"] = float(rt[i] - overall_median)
            features[name + "positive_feedback"] = positive[i]
            # DictVectorizer one-hot encodes named actions; monetary offers remain quantities.
            if (
                task == "social_ultimatum"
                and str(trial["action_taken"]).replace(".", "", 1).isdigit()
            ):
                features[name + "offer"] = float(trial["action_taken"]) / 100
            else:
                features[name + "action"] = actions[i]
            state = trial["state_vector"]
            if task == "delay_disc":
                features[name + "delay"] = float(
                    np.log1p(max(_float(state.get("delay_duration")), 0))
                )
                features[name + "reward_advantage"] = (
                    _float(state.get("delayed_reward")) - _float(state.get("immediate_reward"))
                ) / 100
            if task == "social_ultimatum":
                features[name + "partner_offer"] = _float(state.get("partner_offer")) / 100
                features[name + "partner_offer_present"] = float(
                    _number(state.get("partner_offer")) is not None
                )
        if task == "social_ultimatum":
            for low, high in ((0, 20), (20, 35), (35, 101)):
                selected = [
                    t
                    for t in trials
                    if t["action_taken"] in ("accept", "reject")
                    and low <= _float(t["state_vector"].get("partner_offer")) < high
                ]
                features[prefix + f"accept_offer{low}_{high}"] = (
                    sum(t["action_taken"] == "accept" for t in selected) + 1
                ) / (len(selected) + 2)
        if task == "prob_learning":
            # Recency weighting is fixed a priori; these are features, not fitted traits.
            for alpha in (0.05, 0.2, 0.5, 0.8):
                q = {"A": 0.5, "B": 0.5}
                surprises = []
                choices = []
                for trial in trials:
                    action = trial["action_taken"]
                    choices.append(float(q.get(action, 0.5) >= max(q.values())))
                    outcome = float(_float(trial["reward_received"].get("points")) > 0)
                    surprise = outcome - q.get(action, 0.5)
                    surprises.append(abs(surprise))
                    q[action] = q.get(action, 0.5) + alpha * surprise
                features[prefix + f"greedy_rate_alpha{alpha}"] = _mean(choices)
                features[prefix + f"prediction_error_alpha{alpha}"] = _mean(surprises)
    return features


class AdvancedFeatureView(TransformerMixin, BaseEstimator):
    def __init__(self, view="summary"):
        self.view = view

    def fit(self, X, y=None):
        if self.view not in ("summary", "rich", "sequence", "combined"):
            raise ValueError("Unknown advanced feature view.")
        return self

    def transform(self, X):
        result = []
        for row in X:
            if self.view == "combined":
                result.append(dict(row))
                continue
            if self.view == "summary":
                result.append(
                    {
                        k: v
                        for k, v in row.items()
                        if not any(tag in k for tag in (".advanced.", ".sequence.", ".mechanism."))
                    }
                )
            elif self.view == "rich":
                result.append({k: v for k, v in row.items() if ".sequence." not in k})
            else:
                result.append(
                    {k: v for k, v in row.items() if ".sequence." in k or k.endswith(".n_trials")}
                )
        return result
