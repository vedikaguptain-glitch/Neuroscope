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

These are exploratory results on a repeatedly inspected 156-session cohort whose human, simulated or mixed provenance has not been verified. NEUROSCOPE remains an experimental system; confirmation requires a new cohort.

All benchmarks retain the same participants, binary labels and five outer folds, with seed 42 and three inner folds for model selection. The advanced and rate experiments repeat the inner folds twice. Twelve additional risk-complete partial sessions are used only for training in designated auxiliary candidates. Scaling, model selection, ensemble weights and thresholds are fitted inside the training folds.

The majority baseline is 55.1% (86/156), and the default summary model scores 66.7% (104/156). The advanced ensemble scores 65.4% (102/156), rate supervision scores 67.3% (105/156), and demographics alone score 53.2% (83/156). Experimental predictors are saved separately and do not replace the default automatically.

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

The [website README](web/README.md) covers participant flow, schema, and deployment.

Detailed activity notes are available in [`web/docs/questions.md`](web/docs/questions.md).

## Setup

The tested Python environment is Windows with Python 3.14. Run these commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
copy .env.example .env
```

`requirements-dev.txt` includes the pinned runtime dependencies in `requirements.lock` and Ruff. For other platforms, resolve compatible packages from `requirements.txt`. Set `DATABASE_URL` in the root `.env` to a readable Supabase Postgres URI, including `sslmode=require`. Extraction uses a read-only database connection; offline training and evaluation require neither environment file.

For the website, use Node 24 and run the following from `web`:

```powershell
copy .env.example .env.local
npm ci
npm run dev
```

Configure `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SESSION_SECRET` and `NEXT_PUBLIC_EXPERIMENT_MODE` in `web/.env.local`. Use `demo` for development or `full` for the 240-trial protocol. The website environment is separate from the root database connection. Never expose service-role credentials in browser variables.

## Run the pipeline

Run these from the repository root with the virtual environment activated:

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

The default 40-configuration search uses other-task behavioral summaries without demographics or target-task trials. The 94-configuration behavioral profile adds regularized participant-local policies, stacking and threshold tuning. The conditional-risk experiment also receives the offered risk stimuli at inference, so it answers a different question from behavior-only prediction.

```powershell
python -m ml --evaluate --search-profile behavioral
python -m ml --conditional-risk
python -m ml --covariate-benchmark --jobs 1
```

The context benchmark compares demographics, behavior and their combination, with 16 configurations per input view. To enable the 160-configuration advanced search, install the optional research dependencies. Rate supervision tests 52 configurations using training participants' gamble rates while retaining the original binary evaluation target.

```powershell
python -m pip install -r requirements-research.txt
python -m ml --benchmark --jobs 1
python -m ml --rate-benchmark --jobs 1
```

Pass `--auxiliary-input ml/data/risk_eligible_participants.json` to either of the last two commands to enable training-only auxiliary candidates. Create that separate file with `ml.utils.extract.extract_completed_sessions(eligibility="risk_complete")`; evaluation participants are excluded before augmentation.

Use `--input`, `--output-dir` and `--seed` for isolated, reproducible runs:

```powershell
python -m ml --evaluate --input ml/data/raw_participants.json --output-dir ml/data/optimization_my_run --seed 42
python -m ml --help
```

Combined stages use the newly extracted JSON. The encoder fits normalization and category vocabularies on its training participants, records missing state/reward fields explicitly, uses fixed validation corruption masks, and saves the best validation checkpoint with its preprocessing spec.

## Saved models and data

Raw sessions, processed tensors, embeddings, checkpoints and experiment outputs are gitignored. Extraction writes `ml/data/raw_participants.json`, `processed.pt` and `vocab.json`; the encoder checkpoint is `ml/models/neuroscope_msm.pt`.

Experiments write metrics, participant-level predictions and fitted predictors under `ml/data/optimization_<task>/`, `optimization_advanced_risk_pref/`, `optimization_risk_rate/` or `optimization_covariate_risk/`. The conditional experiment uses `ml/data/conditional_risk_policy/`. An explicit output root isolates these files from earlier runs.

Each experiment retains immutable `runs/<run-id>/` generations with SHA-256 manifests and an atomic `latest.json` pointer. Flat files are compatibility copies. Use `ml.artifacts.resolve_artifact(path)` before reading a committed artifact; checksums detect accidental changes but do not make untrusted pickle/joblib files safe.

Prediction helpers are `ml.utils.optimize.predict_sessions`, `ml.utils.advanced_benchmark.predict_advanced`, `ml.utils.rate_benchmark.predict_rates` and `ml.utils.covariate_benchmark.predict_covariates`. The context helper defaults to the combined model and requires recorded age and school class. All exclude target-task responses.

`ml.utils.inspect_predictors.export_parameters(experiment_directory)` writes readable ensemble weights, coefficients, intercepts and estimator-specific tree importances under `inspection/`. Pass `predictor_name="predictors.joblib"` for the context model. Coefficients apply after preprocessing and describe predictive associations, not causal effects. Private local comparisons and fit diagnostics are in `ml/data/optimization_comparison.json` and `ml/data/optimization_fit_diagnostics/results.json`.

## Checks and maintenance

```powershell
ruff check main.py ml tests
ruff format --check main.py ml tests
python -m unittest discover -s tests -v
```

The 32 Python tests cover target-answer isolation, nested fold coverage, saved-model round trips, interrupted writes, record validation, coefficient export and encoder checkpoint selection. Synthetic test scores validate implementation only. From `web`, run `npm run lint`, `npm test` and `npm run build`; the build also checks TypeScript. CI runs Python on Windows and web checks on Linux without database credentials.

Keep learned transformations inside training folds, retain the original evaluation cohort and labels, and preserve earlier experiment generations. Only extraction needs database access. `ml/config.py` owns paths and protocol constants, `ml/records.py` validates input JSON, and `ml/utils/features.py` computes participant-local predictors independently of Torch and Postgres.

Regenerate the Python lock with uv 0.13.5:

```powershell
uv pip compile requirements.txt --python-version 3.14 --python-platform windows --output-file requirements.lock
```

After dependency changes, run the checks and a separate-output pipeline smoke run. `tmp/backup_database.py` creates and verifies a read-only JSONL ZIP snapshot under `~/Desktop/Neuroscope-backups`; it is a data snapshot, not a `pg_dump` restore archive.

## Optional model attribution

**Built with PriorLabs-TabPFN.** The advanced experiment runs public TabPFN-v2 weights locally, with telemetry and interactive browser login disabled. Participant records are not sent to hosted inference. The weights use the [Prior Labs License](third_party/TabPFN-v2-LICENSE.txt), separately from the package code license. Retain its attribution and naming requirements when sharing assisted models; the export name is **TabPFN-Neuroscope**. See the [upstream project](https://github.com/PriorLabs/TabPFN).
