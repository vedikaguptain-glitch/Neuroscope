# NEUROSCOPE

Web-based behavioral experiment platform for collecting continuous decision-making sequences across five cognitive tasks. Built with Next.js 16 (App Router, Turbopack), jsPsych 8, and Supabase.

## Setup

1. **Node.js 20.9+** (this repo was generated with Node 24).
2. Copy environment variables:

```bash
copy .env.example .env.local
```

Fill in:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (legacy anon key also works)
- `SESSION_SECRET` (long random string used to sign the participant cookie)
- `NEXT_PUBLIC_EXPERIMENT_MODE` — `full` (~40 min) or `demo` (short local testing)

3. Create a Supabase project, then paste `supabase/setup.sql` into the SQL Editor and run it. That creates `participants` and `trials` with **INSERT-only** grants and RLS. The web client cannot `SELECT` either table.

4. Install and run:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Consent → experiment → complete, with no return to a home screen during the battery.

## Data model

Each jsPsych trial writes one row immediately via a Server Action:

`x_t = [state_vector, action_taken, reward_received, reaction_time_ms]`

Task mechanics (reversal flags, discount amounts, hidden rules, ultimatum roles) live in `latent_variables`.

Researchers read data from the Supabase Table Editor or SQL using the service role. `/dashboard` is a reminder of that boundary, not a live data UI.
