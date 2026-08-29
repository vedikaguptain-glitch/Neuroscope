-- Keep participant sessions anonymous by removing the previously collected name.
alter table public.participants
  drop column if exists name;
