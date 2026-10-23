"""Validate research records at the file boundary without ML or database imports."""

import json
import math
from pathlib import Path

from ml.config import RAW_PARTICIPANTS_PATH, TASK_COUNTS


def validate_sessions(sessions: list) -> None:
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("Expected a nonempty array of participant sessions.")
    identities = set()
    for index, session in enumerate(sessions):
        prefix = f"Session {index + 1}"
        if not isinstance(session, dict):
            raise ValueError(f"{prefix} must be an object.")
        identity = session.get("participant_id")
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError(f"{prefix} requires a distinct, nonempty participant_id.")
        identities.add(identity)
        trials = session.get("trials")
        if not isinstance(trials, list) or not trials:
            raise ValueError(f"{prefix} requires a nonempty trial array.")
        seen = set()
        for trial in trials:
            if not isinstance(trial, dict):
                raise ValueError(f"{prefix} has a trial that is not an object.")
            task, position = trial.get("task_id"), trial.get("trial_index")
            if (
                not isinstance(task, str)
                or task not in TASK_COUNTS
                or type(position) is not int
                or not 1 <= position <= TASK_COUNTS[task]
            ):
                raise ValueError(f"{prefix} has an unknown task or out-of-range trial index.")
            key = (task, position)
            if key in seen:
                raise ValueError(f"{prefix} contains a duplicate task/trial index.")
            seen.add(key)
            if not isinstance(trial.get("action_taken"), str) or not trial["action_taken"]:
                raise ValueError(f"{prefix} has an invalid action.")
            reaction_time = trial.get("reaction_time_ms")
            if (
                type(reaction_time) not in (int, float)
                or not math.isfinite(reaction_time)
                or reaction_time < 0
            ):
                raise ValueError(f"{prefix} has an invalid reaction time.")
            for field in ("state_vector", "reward_received"):
                if not isinstance(trial.get(field), dict):
                    raise ValueError(f"{prefix} requires an object for {field}.")
                try:
                    json.dumps(trial[field], allow_nan=False)
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"{prefix} has a non-JSON or nonfinite value in {field}."
                    ) from exc


def load_raw_participants(path: Path | None = None) -> list[dict]:
    source = path or RAW_PARTICIPANTS_PATH
    if not source.exists():
        raise RuntimeError(f"Raw data not found at {source}. Run `python main.py --extract` first.")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read participant JSON at {source}.") from exc
    validate_sessions(payload)
    return payload
