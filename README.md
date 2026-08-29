# NEUROSCOPE

NEUROSCOPE is a student-led research project exploring whether patterns across different kinds of decisions can be studied as one continuous behavioral sequence.

The repository contains the participant-facing data collection system and a self-supervised machine learning pipeline that learns latent representations from completed 240-trial sessions. It does not produce clinical conclusions or assign personality and ability scores.

## Research direction

Most behavioral tasks examine one kind of choice in isolation. NEUROSCOPE instead records how the same participant learns from feedback, responds to uncertainty, weighs time, discovers patterns, and makes social decisions during one session.

The project asks whether those responses share enough structure to support a general representation of decision-making. Each trial is recorded in a consistent form \(x_t = [S_t, A_t, R_t, \Delta t]\) (situation, action, outcome, and response time), while task-specific context remains available for later analysis.

## Current status

The data collection protocol provides:

- Five connected decision activities totaling 240 trials in the full protocol.
- Anonymous participant sessions that do not collect names or direct identifiers.
- Immediate, retryable trial logging with protection against duplicate records.
- A short participant summary at the end that avoids diagnostic or personality claims.
- A demo mode for development and a full mode for research sessions.

The machine learning pipeline can:

- Extract only fully completed 240-trial sessions from Postgres.
- Train a transformer encoder with masked sequence modeling (predict a hidden action or reward).
- Extract frozen session embeddings and linearly probe them for held-out-task generalization.

Until the model is trained on an adequate sample and those results are reported, treat NEUROSCOPE as an experimental system rather than a validated behavioral model.

## Research boundaries

Participation is voluntary, and the website collects age bracket and education level alongside task responses. Participants aged 13–17 must confirm guardian consent. The browser cannot read stored research records, and researchers access them separately through protected database credentials.

The protocol has practical limitations: activity order is fixed, browser storage supports resume only on the same device and profile, and the programmed social partner is not a human participant. Linear-probe scores are research metrics, not diagnoses.

## Repository

| Path | Contents |
|---|---|
| [`web`](web) | Next.js participant website, consent flow, and trial logging |
| [`ml`](ml) | PyTorch transformer, preprocessing, training, and evaluation |
| [`main.py`](main.py) | Single CLI for extract, train, and evaluate |
| [`requirements.txt`](requirements.txt) | Python dependencies for the ML pipeline |
| [`.env.example`](.env.example) | `DATABASE_URL` template for research extraction |

The [website README](web/README.md) covers participant flow, architecture, local setup, schema, testing, and deployment. The [ML README](ml/README.md) covers representation learning, commands, artifacts, and evaluation.

Detailed activity notes are available in [`web/docs/questions.md`](web/docs/questions.md).

## Machine learning (summary)

Run these from the repository root after creating a virtual environment and installing `requirements.txt`. Put a readable Supabase Postgres URI in `.env` as `DATABASE_URL` (see `.env.example`).

```powershell
python main.py --extract
python main.py --train
python main.py --evaluate
```

| Flag | What it does |
|---|---|
| `--extract` | Downloads completed sessions and builds padded 240-step tensors |
| `--train` | Trains the encoder (AdamW, cosine schedule); writes `ml/models/neuroscope_msm.pt` |
| `--evaluate` | Frozen linear probe: predict one activity from embeddings of the other four |

Training options include `--epochs`, `--batch-size`, and `--lr`. Evaluation accepts `--held-out-task` (`prob_learning`, `risk_pref`, `delay_disc`, `rule_discovery`, `social_ultimatum`). The encoder uses CUDA when available and CPU otherwise.

Extracted JSON, processed tensors, and checkpoints are gitignored. Full setup, file map, and scientific caveats are in [`ml/README.md`](ml/README.md).
