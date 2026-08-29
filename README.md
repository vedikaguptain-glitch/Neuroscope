# NEUROSCOPE

**Learning a general latent representation of human decision-making from an unbroken sequence of choices.**

NEUROSCOPE is a web experiment that collects continuous behavioral sequences across five decision tasks, logging each trial as `x_t = [S_t, A_t, R_t, Δt]`.

It is a research data-collection protocol for representation learning. **Not a trained model. Not a clinical or diagnostic system.**

## Result

There is no held-out model score yet. The current result is a roughly 30-minute battery that writes one trial row immediately after every choice, without returning to a menu.

| Module | `task_id` | Full trials |
|---|---|---:|
| Probabilistic learning | `prob_learning` | 60 |
| Risk preference | `risk_pref` | 30 |
| Delay discounting | `delay_disc` | 50 |
| Different patterns: discover the rule that connects them | `rule_discovery` | 60 |
| Social ultimatum | `social_ultimatum` | 40 |

That is 240 decision trials plus consent, comprehension, and demographics. `NEXT_PUBLIC_EXPERIMENT_MODE=demo` shortens each module for local testing and is not a scientific sample.

The web client is INSERT-only. Researchers read `participants` and `trials` from Supabase with the service role. `/dashboard` is a reminder of that boundary, not a live results UI.

A later representation model may be trained on these sequences. Until that evaluation exists, NEUROSCOPE should be judged as a logging protocol, not as a latent-space result.

## Research question

People do not make one isolated choice. They learn under noise, take risk, wait, discover hidden rules, and bargain. Most lab tasks stop at a single paradigm, so the recorded sequence is too narrow to support a general decision embedding.

NEUROSCOPE freezes the session as one continuous stream and asks:

**Does a single participant’s trial-by-trial history across five decision systems contain enough shared structure to learn a general latent representation of decision-making, rather than five separate task models?**

The logged object is the later training target: `x_t = [S_t, A_t, R_t, Δt]`, with task mechanics in `latent_variables`. The protocol does not infer traits in the browser, predict diagnoses, or score “better” decision-makers.

The contribution is a controlled collection design: consent and identity up front, then an unbroken battery with immediate inserts, skippable resume after refresh, and INSERT-only client access.

## Findings

### What the protocol can do

1. **The sequence stays unbroken by construction.** After consent, five jsPsych modules chain automatically. There is no home screen between tasks. Refresh resume skips completed trials from `sessionStorage` so the logged index does not restart at zero.

2. **Every choice is the same tensor shape.** State, action, reward, and reaction time are written on each trial. Reversal flags, discount amounts, hidden rules, and ultimatum roles live in `latent_variables`, so a later model can condition on mechanism without changing the core `x_t` schema.

3. **The five modules are complementary, not duplicates.** Probabilistic learning is noisy two-armed choice with a mid-session reversal. Risk preference varies gamble parameters against a safe amount. Delay discounting titrates now vs later. Rule discovery shifts an unstated matching rule. Ultimatum alternates proposer and responder against a programmed partner.

4. **Write path is immediate and retrying.** Each trial is inserted through a server action and a client queue with bounded retries. Duplicate `(participant, task, trial_index)` rows are treated as success so a retry cannot fork the sequence.

### Where it is weak

5. **Collection is not representation learning.** Logging `x_t` does not prove that a useful latent exists. There is no embedding, no held-out participant evaluation, and no comparison against task-specific baselines.

6. **The session is anonymous.** The app does not collect names. Trials are keyed by a hashed `participant_id` and a signed cookie so responses can remain grouped without identifying the participant.

7. **Client-side progress is not the database of record.** Resume state lives in `sessionStorage`. Closing the browser ends the session. Failed inserts are counted on the complete screen, but the participant cannot repair them.

8. **Demo mode is not a subsample of the scientific protocol.** It only shortens timelines. Do not mix `demo` and `full` rows in the same analysis without tagging the mode.

## Experimental setup

**Target.** A continuous decision sequence suitable for later representation learning.

**Session constraint.** Consent, comprehension, age bracket, and education are collected before the first trial. Ages 13–17 also require guardian consent.

**Tasks.** Full mode uses 60 / 30 / 50 / 60 / 40 trials in a fixed order: probabilistic learning, risk, delay, pattern discovery, ultimatum. Stimuli that need randomness are seeded from the hashed participant id.

**Logging.** Each jsPsych trial calls `logTrial` with `state_vector`, `action_taken`, `reward_received`, `reaction_time_ms`, and `latent_variables`. The cookie binds the insert to the session that consent created.

**Access.** Anon and authenticated roles may INSERT into `participants` and `trials`. They cannot SELECT, UPDATE, or DELETE. Service role is for researchers.

**Stack.** Next.js 16 (App Router), jsPsych 8, Supabase Postgres, Zod-validated server actions.

## Limitations

* No trained model or published latent-space metric exists in this repository.
* Age bracket and education are stored, while names and direct identifiers are not collected.
* INSERT-only RLS means the web app cannot show researchers their own tables.
* `sessionStorage` resume does not survive a new browser profile or a cleared site.
* Task order is fixed, so later modules can carry fatigue from earlier ones.
* The programmed ultimatum partner is not a human counterpart.

## Exhibit

The exhibit is the experiment itself:

* `/` — consent, comprehension, and demographics.
* `/experiment` — the five-module battery.
* `/complete` — hashed participant id, session points, unsaved-trial count.
* `/dashboard` — researcher boundary note, not a results console.

Protocol detail is in [`docs/questions.md`](docs/questions.md). Schema and grants are in [`supabase/setup.sql`](supabase/setup.sql).

## Running

Install Node.js 20.9+, then from the repository root:

```powershell
copy .env.example .env.local
npm install
npm run dev
```

Fill in:

* `NEXT_PUBLIC_SUPABASE_URL`
* `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (legacy anon key also works)
* `SESSION_SECRET` (long random string used to sign the participant cookie)
* `NEXT_PUBLIC_EXPERIMENT_MODE` — `full` (~40 min) or `demo` (short local testing)

Create a Supabase project, then paste [`supabase/setup.sql`](supabase/setup.sql) into the SQL Editor and run it. That creates `participants` and `trials` with INSERT-only grants and RLS. Existing projects that collected names should run [`supabase/migrations/20260829090000_remove_participant_name.sql`](supabase/migrations/20260829090000_remove_participant_name.sql).

Open [http://localhost:3000](http://localhost:3000). Consent → experiment → complete.

```powershell
npm test
npm run build
```

Never put the Supabase `service_role` key in `.env.local`.

## Outputs

* `public.participants`: session row with hashed `participant_id`, `age_bracket`, `education_level`, `session_start_timestamp`, `comprehension_passed`.
* `public.trials`: one `x_t` row per choice, tagged with `task_id` and `trial_index`.
* Researchers inspect both tables in the Supabase Table Editor or SQL using the service role.

## Repository layout

* [`app`](app): pages, layouts, and server actions.
* [`components/consent`](components/consent): consent, comprehension, and demographics.
* [`components/experiment`](components/experiment): jsPsych host and client session bootstrap.
* [`lib/experiment`](lib/experiment): timelines, task logic, plugins, trial queue.
* [`lib/supabase`](lib/supabase): browser and server clients.
* [`supabase`](supabase): setup SQL and migrations.
* [`docs/questions.md`](docs/questions.md): protocol details.

## Acknowledgments and sources

NEUROSCOPE implements the continuous battery described in [`docs/questions.md`](docs/questions.md), with frontend sequencing and INSERT-only logging split across the web client and Supabase. The consent flow is written as an IRB-style gate, not as a substitute for board approval. jsPsych provides the trial runtime. These references do not imply endorsement by any review board, school, or lab.
