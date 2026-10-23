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
- Select cross-task behavioral predictors using nested participant cross-validation.
- Extract frozen session embeddings for a separate exploratory linear-probe diagnostic.

## Measured risk-prediction results

**92.9% training-set accuracy (145/156 sessions); 68.6% nested cross-validation accuracy (107/156 sessions).** These measurements come from the combined behavioral, age and school-class random forest benchmark, evaluated on 23-24 October 2026. The target is whether a session includes gambling on at least 15 of its 30 risk trials; those risk responses are excluded from prediction inputs.

Training-set accuracy measures the saved model's fit to sessions already used to train it. The five-fold nested participant cross-validation result measures predictions for participants excluded from each outer training fold. The 24.4 percentage-point gap indicates substantial overfitting, so **92.9% is not an estimate of accuracy on new participants**. The 85% held-out target was not reached, and the highest observed behavior-only cross-validation accuracy is 67.3%.

These are exploratory results on a repeatedly inspected 156-session cohort whose human, simulated or mixed provenance has not been verified. NEUROSCOPE remains an experimental system. See the [benchmark results](ml/BENCHMARK_RESULTS.md) for input scopes, evaluation details and limitations.

With the trusted local data and saved model artifacts present, reproduce the training-fit measurements with:

```powershell
python -m ml.utils.fit_diagnostics
```

The command verifies the cohort hash and records exact counts, fitted-model checksums and corresponding cross-validation results in `ml/data/optimization_fit_diagnostics/`. Participant data and model artifacts are gitignored and are not distributed with the repository.

## Research boundaries

Participation is voluntary, and the website collects age from 14 to 18 and school class from IX to XII alongside task responses. Participants aged 13–17 must confirm guardian consent. The browser cannot read stored research records, and researchers access them separately through protected database credentials.

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

Development setup, module boundaries, reproducible runs and CI checks are documented
in [CONTRIBUTING.md](CONTRIBUTING.md). For the tested Windows/Python 3.14 environment,
install `requirements.lock`; `requirements-dev.txt` adds the development checker.

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
| `--evaluate` | Select cross-task predictors with nested participant cross-validation |
| `--probe` | Exploratory frozen-embedding probe; pretraining participants can overlap |

Training options include `--epochs`, `--batch-size`, and `--lr`. Nested evaluation accepts
`--held-out-task` (`risk_pref`, `delay_disc`, `social_ultimatum`); the exploratory `--probe`
also supports `prob_learning` and `rule_discovery`. The encoder uses CUDA when available
and CPU otherwise.

Extracted JSON, processed tensors, and checkpoints are gitignored. Full setup, file map, and scientific caveats are in [`ml/README.md`](ml/README.md).
