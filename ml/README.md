# NEUROSCOPE machine learning pipeline

This directory contains the self-supervised model that learns a latent representation of decision-making from completed 240-trial sessions. The participant website in [`web`](../web) collects the data. Run the pipeline from the **repository root** with `main.py`.

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

`--evaluate` loads the checkpoint, encodes each session **without** the held-out activity visible to attention, and trains a scikit-learn logistic regression on the frozen pooled embedding to predict that activity’s behavior (default `risk_pref`: gamble rate ≥ 0.5). Choose the held-out activity with `--held-out-task`.

You can chain flags, for example `python main.py --extract --train --evaluate`.

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
