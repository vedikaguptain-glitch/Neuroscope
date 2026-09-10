-- Exact age and school class are required for the student study.
-- Grouped demographic values cannot be converted to exact values safely.
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'participants'
      and column_name = 'age_bracket'
  ) and exists (select 1 from public.participants limit 1) then
    raise exception
      'participants contains rows; export or remove test sessions before replacing grouped demographics';
  end if;
end
$$;

alter table public.participants
  drop column if exists age_bracket,
  drop column if exists education_level,
  add column if not exists age smallint,
  add column if not exists school_class smallint,
  add column if not exists session_completed_timestamp timestamptz;

alter table public.participants
  alter column age set not null,
  alter column school_class set not null,
  drop constraint if exists participants_age_check,
  drop constraint if exists participants_school_class_check,
  add constraint participants_age_check check (age between 14 and 18),
  add constraint participants_school_class_check check (school_class between 9 and 12);

create or replace function public.complete_participant_session(
  target_participant_id uuid
)
returns boolean
language sql
security definer
set search_path = public, pg_temp
as $$
  update public.participants
  set session_completed_timestamp = coalesce(session_completed_timestamp, now())
  where id = target_participant_id
  returning true;
$$;

revoke all on function public.complete_participant_session(uuid) from public;
grant execute on function public.complete_participant_session(uuid)
  to anon, authenticated, service_role;
