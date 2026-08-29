# NEUROSCOPE website

This directory contains the participant-facing website for the NEUROSCOPE research project. It handles consent, demographics, five continuous decision activities, per-trial data collection, session recovery, and the final participant summary.

For the broader research question and project status, see the [repository README](../README.md).

## Participant flow

The website keeps the study intentionally simple for participants:

1. The landing page explains that this is a student-led research activity without exposing the project’s full analytical design.
2. Participants accept the consent terms and answer short comprehension checks.
3. Age bracket and education level are collected; names are not requested or stored.
4. Five activities run as one continuous sequence without returning to a menu.
5. The completion page shows points and session-specific statistics without making personality, ability, or clinical claims.

Full mode contains 240 decision trials:

| Activity | `task_id` | Trials |
|---|---|---:|
| Probabilistic learning | `prob_learning` | 60 |
| Risk preference | `risk_pref` | 30 |
| Delay discounting | `delay_disc` | 50 |
| Different patterns: discover the rule that connects them | `rule_discovery` | 60 |
| Social decision-making | `social_ultimatum` | 40 |

`NEXT_PUBLIC_EXPERIMENT_MODE=demo` shortens the timelines for development. Demo sessions are not interchangeable with full research sessions.

## Technical design

The site uses Next.js 16 with the App Router, React 19, jsPsych 8, Tailwind CSS 4, Zod, and Supabase Postgres.

Each activity produces the same core trial payload:

- `state_vector` describes what the participant saw.
- `action_taken` records the response.
- `reward_received` records the outcome.
- `reaction_time_ms` records the response time.
- `latent_variables` retains activity-specific context for later analysis.

Trials enter a persistent client queue and are written through validated server actions. The queue retries failed inserts, while the unique participant/activity/trial index prevents retries from creating duplicate data.

Progress and summary statistics are stored in browser session and local storage so a refresh can skip completed trials. The database remains the research record; browser progress only supports the participant experience.

## Privacy and access

Participant sessions use a random internal UUID, a hashed public ID, and a signed session cookie. The application does not collect names.

The Supabase client roles can insert participant and trial rows but cannot select, update, or delete them. Researchers inspect the data separately with service-level access. Never expose the Supabase service-role key in the website environment.

## Routes

- `/` provides consent, comprehension checks, and demographics.
- `/experiment` hosts the continuous jsPsych activity sequence.
- `/complete` displays the participant’s session snapshot and save status.
- `/dashboard` explains that research records are unavailable through the participant website.

## Local setup

Install Node.js 20.9 or newer, then run these commands from this `web` directory:

```powershell
copy .env.example .env.local
npm install
npm run dev
```

Configure the following environment variables:

```text
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
SESSION_SECRET=
NEXT_PUBLIC_EXPERIMENT_MODE=demo
```

`SESSION_SECRET` should be a long random value. `NEXT_PUBLIC_EXPERIMENT_MODE` accepts `demo` or `full`.

Open [http://localhost:3000](http://localhost:3000) after the development server starts.

## Database setup

Create a Supabase project and run [`supabase/setup.sql`](supabase/setup.sql) in the SQL editor. It creates the `participants` and `trials` tables, indexes, grants, and insert-only row-level security policies.

For an existing database that previously stored participant names, apply [`supabase/migrations/20260829090000_remove_participant_name.sql`](supabase/migrations/20260829090000_remove_participant_name.sql).

The primary outputs are:

- `public.participants`, containing the anonymous session ID, demographics, start time, and comprehension status.
- `public.trials`, containing one normalized row for every completed decision.

## Verification

Run the project checks from this directory:

```powershell
npm run lint
npm test
npm run build
```

## Directory layout

- [`app`](app) contains pages, layouts, styles, and server actions.
- [`components`](components) contains consent, experiment, and shared interface components.
- [`lib/experiment`](lib/experiment) contains activity logic, timelines, plugins, session state, and the logging queue.
- [`lib/supabase`](lib/supabase) contains the browser and server database clients.
- [`supabase`](supabase) contains the schema and migrations.
- [`docs/questions.md`](docs/questions.md) contains the detailed activity protocol.

When deploying from a repository-level platform configuration, set the application root directory to `web`.
