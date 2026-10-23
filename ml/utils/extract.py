"""Extract fully completed 240-trial experiments from Postgres."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.utils.db import connect
from ml.config import RAW_PARTICIPANTS_PATH
from ml.artifacts import write_json
from ml.records import validate_sessions

COMPLETED_SESSIONS_CTE = """
with fully_done as (
  select p.id
  from public.participants as p
  join public.trials as t
    on t.participant_id = p.id
  group by p.id
  having
    count(*) = 240
    and count(*) filter (where t.task_id = 'prob_learning') = 60
    and count(*) filter (where t.task_id = 'risk_pref') = 30
    and count(*) filter (where t.task_id = 'delay_disc') = 50
    and count(*) filter (where t.task_id = 'rule_discovery') = 60
    and count(*) filter (where t.task_id = 'social_ultimatum') = 40
)
"""

SESSION_SELECT_SQL = """
select coalesce(
  jsonb_agg(
    jsonb_build_object(
      'participant_id', p.participant_id,
      'age', p.age,
      'school_class', p.school_class,
      'session_started_at', p.session_start_timestamp,
      'trials', (
        select jsonb_agg(
          jsonb_build_object(
            'task_id', t.task_id,
            'trial_index', t.trial_index,
            'state_vector', t.state_vector,
            'action_taken', t.action_taken,
            'reward_received', t.reward_received,
            'reaction_time_ms', t.reaction_time_ms,
            'latent_variables', t.latent_variables,
            'created_at', t.created_at
          )
          order by
            case t.task_id
              when 'prob_learning' then 1
              when 'risk_pref' then 2
              when 'delay_disc' then 3
              when 'rule_discovery' then 4
              when 'social_ultimatum' then 5
            end,
            t.trial_index
        )
        from public.trials as t
        where t.participant_id = p.id
      )
    )
    order by p.session_start_timestamp
  ),
  '[]'::jsonb
) as fully_done_experiments
from public.participants as p
join fully_done as done
  on done.id = p.id;
"""

EXTRACT_SQL = COMPLETED_SESSIONS_CTE + SESSION_SELECT_SQL
RISK_COMPLETE_SQL = (
    """
with fully_done as (
  select participant_id as id from public.trials
  group by participant_id
  having count(*) filter (where task_id = 'risk_pref') = 30
)
"""
    + SESSION_SELECT_SQL
)


def _parse_payload(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        parsed: Any = json.loads(value)
    else:
        parsed = value
    if not isinstance(parsed, list):
        raise RuntimeError("Extraction query did not return a JSON array.")
    return parsed


def extract_completed_sessions(
    output_path: Path | None = None, *, eligibility: str = "full"
) -> Path:
    """Download completed sessions and write them to raw_participants.json."""
    if eligibility not in ("full", "risk_complete"):
        raise ValueError("Unknown session eligibility rule.")
    destination = output_path or (
        RAW_PARTICIPANTS_PATH
        if eligibility == "full"
        else RAW_PARTICIPANTS_PATH.with_name("risk_eligible_participants.json")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(EXTRACT_SQL if eligibility == "full" else RISK_COMPLETE_SQL)
            row = cursor.fetchone()

    payload = _parse_payload(row[0] if row else None)
    if not payload:
        raise RuntimeError("No complete sessions were found; the previous extraction was retained.")
    validate_sessions(payload)
    write_json(destination, payload)
    return destination
