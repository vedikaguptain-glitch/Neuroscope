-- Store the participant's name with each session.
alter table public.participants
  add column if not exists name text not null default 'Unknown';

alter table public.participants
  alter column name drop default;
