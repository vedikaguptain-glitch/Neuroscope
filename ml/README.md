# NEUROSCOPE machine learning pipeline

This directory contains the self-supervised model that learns a latent representation of decision-making from completed 240-trial sessions. The participant website in [`web`](../web) collects the data. Run the pipeline from the **repository root** with `main.py`.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the dependency lock, module boundaries,
automated checks, isolated output paths and checksummed experiment generations.

The model does not produce clinical conclusions or personality scores. Until it is trained and evaluated on a sufficient sample, treat it as experimental research code rather than a validated behavioral model.

## What it learns

Each trial is a step \(x_t = [S_t, A_t, R_t, \Delta t]\):

| Symbol | Field | Role |
|---|---|---|
| \(S_t\) | `state_vector` | What the participant saw |
| \(A_t\) | `action_taken` | The response |
| \(R_t\) | `reward_received` | The outcome |
| \(\Delta t\) | `reaction_time_ms` | Response time |

A session is one 240-step sequence across five activities (`prob_learning`, `risk_pref`, `delay_disc`, `rule_discovery`, `social_ultimatum`). Extraction keeps only participants who finished every trial in those counts (60 / 30 / 50 / 60 / 40).

Training uses masked sequence modeling: at a subset of real trials the model hides either the action or the reward and must predict the missing value. After training, frozen encoder states are linearly probed to predict behavior on a held-out activity from the other four.

## Layout

```text
ml/
  data/          # extracted JSON, tensors, embeddings (gitignored)
  models/        # architectures and saved checkpoints (weights gitignored)
  utils/         # database, preprocess, dataset, MSM, train, infer, evaluate
```

| Path | Role |
|---|---|
| `utils/db.py` | Loads `DATABASE_URL` and opens Postgres |
| `utils/extract.py` | Downloads fully completed sessions |
| `utils/preprocess.py` | Vocabularies, RT normalization, padded \(x_t\) tensors |
| `utils/dataset.py` | PyTorch `Dataset` and train/validation loaders |
| `models/embeddings.py` | Fused timestep embedding and absolute positional encoding |
| `models/transformer.py` | 4-layer encoder (`d_model=128`, 4 heads) |
| `utils/msm.py` | Masking and action/reward losses |
| `utils/train.py` | AdamW, cosine schedule, checkpointing |
| `utils/infer.py` | Hidden-state and pooled session embeddings |
| `utils/evaluate.py` | Frozen linear probe for a held-out task |

Run `python main.py --help` from the repository root for flags.

## Setup

Use Python 3.14 (or another version with wheels for the packages in `requirements.txt`). From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `DATABASE_URL` in `.env` to the Supabase Postgres URI (Database settings → URI), including `sslmode=require`. Do not commit `.env`. Website keys in `web/.env.local` are not a substitute; extraction needs a connection that can **read** `participants` and `trials`.

PyTorch uses CUDA when it is available and CPU otherwise.

## Commands

All commands run from the repository root, with the virtual environment activated.

```powershell
python main.py --extract
python main.py --train
python main.py --evaluate
```

`--extract` writes `ml/data/raw_participants.json` and preprocesses it to `ml/data/processed.pt` plus `ml/data/vocab.json`.

`--train` reads those tensors, trains the transformer, and writes `ml/models/neuroscope_msm.pt`. Useful options: `--epochs` (default 10), `--batch-size` (default 4), `--lr` (default `3e-4`).

`--evaluate` selects supervised behavioral predictors using nested participant cross-validation
(default `risk_pref`: gamble rate ≥ 0.5). This uses the other four tasks and does not
require an encoder checkpoint. Choose the target with `--held-out-task`.

`--probe` runs the older exploratory diagnostic: load the encoder checkpoint, encode each
session without the held-out activity visible to attention, and linearly probe the frozen
pooled embeddings. Its pretraining and evaluation participants can overlap.

You can chain flags, for example `python main.py --extract --train --evaluate`.

## Optimized cross-task prediction

Run `python main.py --evaluate` (or its alias `--optimize`) after extraction to select predictors of the original
binary risk-preference target, gambling on at least half of that participant's trials.
This is a supervised behavioral predictor, separate from the self-supervised encoder.
It uses response-time distributions, task-specific choice rates, within-task changes,
feedback responses, and condition sensitivities from the other four tasks. Target-task
trials, demographics, participant identifiers and dates are excluded from predictors.

The fixed search compares 40 configurations of majority prediction, regularized logistic
regression, RBF SVM, shrinkage discriminant analysis, random forests and extra trees.
Five outer participant folds estimate performance; three inner folds select both model
family and hyperparameters by accuracy. Dictionary vectorization and scaling are fitted
inside each training fold. The majority baseline also uses training labels only.
Reported accuracy aggregates every participant's out-of-fold prediction. AUC is averaged
within folds because selected classifiers can have different score scales.

```powershell
python main.py --optimize
python main.py --optimize --held-out-task delay_disc
python main.py --optimize --held-out-task social_ultimatum
```

For social prediction, the target is acceptance on at least half of responder trials;
proposer offers are excluded from its denominator. `--outer-folds`, `--inner-folds` and
`--jobs` control cross-validation and parallelism. The default seed is fixed at 42.

Artifacts are saved under `ml/data/optimization_<task>/`: `results.json`, hashed
participant-level `predictions.json`, the all-data selection ranking in
`selection_scores.json`, and `predictor.joblib`. The saved predictor is selected by
cross-validation and then fitted on all participants for future use; its selection
score is not an independent evaluation. `ml.utils.optimize.predict_sessions` applies
it to new sessions, ignoring any target-task trials. Load only trusted joblib files.

`weights_and_biases.json` exports the deployment model and each outer-fold model.
Linear feature coefficients describe a one-training-standard-deviation change in an
input, conditional on the other inputs. Intercepts and learned decision cutoffs are
reported separately. These are predictive associations, not causal effects or
validated personality measurements.

### Behavioral weights and bias experiments

```powershell
python main.py --evaluate --search-profile behavioral
python main.py --conditional-risk
```

The `behavioral` profile compares 94 configurations, retaining the original 40 and
adding prior-regularized participant-local choice policies, gradient boosting, a
cross-validated decision cutoff and task-wise stacking. Policy parameters describe
reward/delay sensitivity, previous-choice effects, feedback responses, spatial
preference and rule adaptation. A fixed recency learner supplies one feedback-value
feature; its learning rate is not a fitted psychological parameter. The shared
zero-centered Gaussian prior shrinks policy coefficients and intercepts, including
for participants who always make the same choice. These are exploratory features.

Stacking learns its task weights and intercept from out-of-fold training predictions.
Cutoff tuning refits the complete input pipeline inside its own training folds. Both
remain inside outer participant validation. Expanded-profile artifacts use
`ml/data/optimization_<task>_behavioral/`; the stronger observed summary profile remains
the default rather than automatically replacing it with a more complex model.

The conditional risk experiment asks a different question. It knows the offered
gamble probabilities, payouts and safe-option position at inference, alongside the
other four activities. It fits a regularized trial-level logistic policy, optionally
allowing behavioral features to change the expected-value slope, and aggregates its
choice probabilities into the original participant target. Risk-task test actions,
outcomes and reaction times never enter prediction. Its 69-configuration inner search
also includes a stimulus-only model, which is evaluated separately on the same outer
participants. Results, hashed predictions, coefficients, training feature scales and
the fitted model are stored under `ml/data/conditional_risk_policy/`.

Conditional accuracy must be reported with its stimulus-only baseline and cannot be
presented as strict cross-task accuracy: it uses more input information and more
detailed training responses. Its count probabilities assume conditional independence
and need calibration on new participants. Pure participant-local behavioral feature
calculations are cached for speed; cohort normalization and label-based selection
are refitted inside each training fold.

These remain exploratory internal estimates on the existing sample. They are not
directly comparable to the older single-split embedding probe and need confirmation
in a new cohort after any data-driven feature development. Do not choose an outer
fold or a target task post hoc and present it as the overall result.

## Advanced 85% target benchmark

Install `requirements-research.txt` to enable the advanced CPU experiment. The target
remains gambling on at least 15 of the same 30 risk trials; every evaluation participant
is retained. The benchmark compares 160 fixed configurations across summary, windowed,
and trial-sequence features, including regularized/sparse logistic regression, SVM,
shrinkage LDA, neighbors, PCA, feature selection, CatBoost, XGBoost, LightGBM, forests,
and local TabPFN-v2 predictions. The primary arm is a nonnegative weighted ensemble;
the best inner-selected single model and top-five average are separate recorded arms.

```powershell
python -m pip install -r requirements-research.txt
python -m ml --benchmark --auxiliary-input ml/data/risk_eligible_participants.json
```

The optional auxiliary file contains sessions with all 30 risk trials even if later
activities were unfinished. Evaluation participants are removed from that file before
augmentation, and only candidates explicitly configured for augmentation use the
remaining records. The existing complete-session benchmark cohort does not change.
`extract_completed_sessions(eligibility="risk_complete")` creates this separate JSON;
it does not replace the full-session extraction.

Each outer fold uses repeated inner participant folds to create candidate prediction
vectors. Ensemble weights and the classification threshold are learned from those
training predictions. Candidate caches are tied to the cohort, auxiliary data, source,
library versions and split configuration, and let interrupted runs resume. Results,
all arm predictions, the target-met flag, ensemble weights and the fitted predictor
are saved under `ml/data/optimization_advanced_risk_pref/` using retained generations.
`predict_advanced` loads a checksummed predictor and ignores target-task responses.

This is still exploratory development on an already inspected cohort. Repeated searches
do not turn internal validation into an independent replication. The 85% goal is recorded
as achieved only when the primary whole-cohort accuracy reaches it, not from a selected
fold, an in-sample score, a different metric, or a reduced subset of participants.

**Built with PriorLabs-TabPFN.** This optional experiment runs the publicly downloadable
TabPFN-v2 classifier locally with telemetry and interactive browser login disabled.
Participant records are not sent to a hosted inference service. Its weights use the
[Prior Labs License](../third_party/TabPFN-v2-LICENSE.txt), separately from the package's
code license. Follow that license's attribution and naming requirements before sharing
TabPFN-assisted models; the export name for such an ensemble is **TabPFN-Neuroscope**.
See the [upstream project](https://github.com/PriorLabs/TabPFN) for model attribution.

An additional training strategy preserves the same held-out binary target but uses
the continuous gamble rate for training supervision:

```powershell
python -m ml --rate-benchmark --auxiliary-input ml/data/risk_eligible_participants.json
```

This fixed 52-configuration experiment compares ridge and elastic-net regression,
kernel ridge, partial least squares and extra trees. Its nonnegative ensemble weights
are fitted to inner out-of-fold rate predictions, and its classification threshold
uses outer-training labels only. Target-task rates are never input features or read
during prediction. Models, weights, full-cohort predictions and metrics are stored in
`ml/data/optimization_risk_rate/`; use `predict_rates` to apply a trusted predictor.
Neither benchmark replaces the incumbent summary predictor automatically.

To test developmental context separately, run:

```powershell
python -m ml --covariate-benchmark --jobs 1
```

This compares demographics alone, behavior alone, and their combination using 16
configurations per arm and nested participant folds. Age and school class are explicit
inputs in the context arms, so their accuracy is a different claim from behavior-only
prediction. Participant-local feature dictionaries are computed once; vectorization,
scaling and model selection still happen inside each training fold. Saved pipelines
accept raw sessions at inference and exclude target-task answers. Results are under
`ml/data/optimization_covariate_risk/`.
Use `predict_covariates(path_to_predictors_joblib, sessions)` to apply its combined
model, or select `view="behavior"` / `view="demographics"` explicitly.

`ml.utils.inspect_predictors.export_parameters(experiment_directory)` writes readable
ensemble weights, component coefficients, intercepts and tree importances under
`inspection/`, with retained checksummed generations. For the covariate experiment,
pass `predictor_name="predictors.joblib"`. These are parameters of full-cohort deployment
fits; coefficient signs are predictive associations, not causal effects.

The origin of the stored sessions has not been verified as human, simulated or mixed.
Treat these benchmarks as results on the recorded cohort until collection provenance
is established.

## Encoder training corrections

New preprocessing specs use version 2: numeric state and reward features are normalized,
categories use one-hot encoding, state missingness is explicit, and absent reward fields
are excluded from the masked reward loss. Normalization and vocabularies are fitted on
the encoder's training participants only. Previously saved version-1 checkpoints still
load with their original encoding.

Validation uses the same corruption masks each epoch without resetting the training
random stream. Training retains the best validation checkpoint instead of overwriting
it with the final epoch. The checkpoint stores its own preprocessing spec, which is
used by the embedding probe. The `--probe` command is explicitly an exploratory
probe because encoder pretraining and probe evaluation participants can overlap;
use `--optimize` for participant-separated prediction estimates.

Run the synthetic-data regression suite with
`python -m unittest discover -s tests -v`. It checks target-task isolation, saved
predictor round trips, nested fold coverage, missing reward masking, and best-checkpoint
selection with fixed validation randomness. Additional tests recover known coefficients
in synthetic logistic data, check finite shrinkage under constant choices, reload
stacked/threshold models, and verify that conditional predictions ignore test answers
while responding to changes in offered gambles. Synthetic coefficient recovery checks
the fitting implementation; it does not establish identifiability in the real tasks.

## Artifacts (not in git)

| File | Contents |
|---|---|
| `ml/data/raw_participants.json` | Completed sessions from Postgres |
| `ml/data/processed.pt` | Padded tensors and participant ids |
| `ml/data/vocab.json` | Feature spec and discrete vocabs |
| `ml/data/embeddings.pt` | Optional saved hidden states |
| `ml/models/neuroscope_msm.pt` | Weights, spec, and training metrics |

## Research boundaries

Linear-probe accuracy on a small sample is not evidence of a general decision-making representation. Held-out evaluation asks whether structure learned from four activities predicts behavior on the fifth; it does not validate the protocol for clinical or admissions use.
