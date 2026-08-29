-- NEUROSCOPE schema, grants, and INSERT-only RLS.
-- Paste this entire file into the Supabase SQL Editor (SQL → New query).

create extension if not exists pgcrypto;

create table if not exists public.participants (
  id uuid primary key default gen_random_uuid(),
  participant_id text not null unique,
  age_bracket text not null,
  education_level text not null,
  session_start_timestamp timestamptz not null default now(),
  comprehension_passed boolean not null default false,
  constraint participants_age_bracket_check
    check (age_bracket in ('13-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+')),
  constraint participants_education_level_check
    check (
      education_level in (
        'high_school',
        'some_college',
        'bachelors',
        'masters',
        'doctoral',
        'other'
      )
    )
);

create table if not exists public.trials (
  id uuid primary key default gen_random_uuid(),
  participant_id uuid not null references public.participants (id) on delete cascade,
  task_id text not null,
  trial_index integer not null,
  state_vector jsonb not null default '{}'::jsonb,
  action_taken text not null,
  reward_received jsonb not null default '{}'::jsonb,
  reaction_time_ms double precision not null,
  latent_variables jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint trials_task_id_check
    check (
      task_id in (
        'prob_learning',
        'risk_pref',
        'delay_disc',
        'rule_discovery',
        'social_ultimatum'
      )
    ),
  constraint trials_trial_index_check check (trial_index >= 0),
  constraint trials_rt_check check (reaction_time_ms >= 0),
  constraint trials_unique_index unique (participant_id, task_id, trial_index)
);

create index if not exists trials_participant_created_idx
  on public.trials (participant_id, created_at);

create index if not exists trials_task_id_idx
  on public.trials (task_id);

alter table public.participants
  drop column if exists name;

alter table public.participants enable row level security;
alter table public.trials enable row level security;

revoke all on table public.participants from anon, authenticated, public;
revoke all on table public.trials from anon, authenticated, public;

grant insert on table public.participants to anon, authenticated;
grant insert on table public.trials to anon, authenticated;

grant all on table public.participants to service_role;
grant all on table public.trials to service_role;

drop policy if exists "anon_insert_participants" on public.participants;
create policy "anon_insert_participants"
  on public.participants
  for insert
  to anon, authenticated
  with check (comprehension_passed = true);

drop policy if exists "anon_insert_trials" on public.trials;
create policy "anon_insert_trials"
  on public.trials
  for insert
  to anon, authenticated
  with check (true);

comment on table public.participants is
  'Anonymized experiment sessions. Web clients may INSERT only.';
comment on table public.trials is
  'Per-trial x_t = [S_t, A_t, R_t, dt] logs. Web clients may INSERT only.';
