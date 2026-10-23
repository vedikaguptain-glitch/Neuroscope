# Working on NEUROSCOPE

The supported reproducible Python environment is Windows with Python 3.14. Create
a virtual environment and install `requirements-dev.txt`; it includes the resolved
Windows dependencies in `requirements.lock` and the pinned Ruff version. For other
platforms, resolve from `requirements.txt`, which declares compatible version ranges.
The web project uses Node 24 or newer; CI and `.node-version` select Node 24.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
ruff check main.py ml tests
ruff format --check main.py ml tests
python -m unittest discover -s tests -v
```

From `web`, run `npm ci`, `npm run lint`, `npm test` and `npm run build`.
The tests cover task logic, and the production build checks TypeScript. CI runs these
checks on every push and pull request without database credentials, using separate
Python/Windows and web/Linux jobs. Run `npm audit` separately when reviewing web
dependencies; dependency upgrades belong in a web change.

Enrollment is intentionally anonymous. The database policies grant insert-only access
to public API roles and block record reads and edits through those roles; they do not
establish that each submission came from a unique human. A collection protocol needing
stronger provenance requires a reviewed change to server write credentials and abuse
controls. Scanner warnings about missing login at enrollment should be assessed against
this intended protocol, while trial server actions must retain their signed-cookie check.

## Module boundaries

`ml/config.py` defines paths and protocol constants without third-party dependencies.
`ml/records.py` validates the research JSON boundary. `ml/utils/features.py` computes
participant-local features and targets; it does not import Torch or Postgres.
`ml/utils/optimize.py` owns model selection, and `conditional_policy.py` owns the
separate stimulus-aware experiment. Only extraction imports the database connector.
Preprocessing and encoder code remain independent of a configured database.

Keep transformations that learn cohort statistics inside their training folds.
Do not use target-task answers, outcomes, or response times in held-out predictors.
The conditional experiment may use known risk stimuli; its distinct input contract
and stimulus-only baseline must remain explicit. Synthetic records in tests must
not be replaced with participant data or credentials.

## Running reproducible experiments

Both `python main.py` and `python -m ml` accept the existing stage flags.
`--seed` fixes model/split randomness, `--input` selects a participant JSON file and
`--output-dir` isolates new outputs. For example:

```powershell
python -m ml --evaluate --input ml/data/raw_participants.json --seed 42 --output-dir ml/data/optimization_my_run
```

When combining stages, extraction's new JSON is passed to later stages. Model output
goes under `models/`, and each evaluation gets a separate experiment directory inside
the selected output root. Raw records, tensors, checkpoints and experiment outputs
are private local artifacts. The root `.env` provides extraction's `DATABASE_URL`;
the web app separately reads `web/.env.local`. Offline stages require neither.

New experiment directories retain immutable `runs/<run-id>/` generations with a
SHA-256 manifest. `latest.json` identifies the committed generation. Flat files are
compatibility copies; use `ml.artifacts.resolve_artifact(path)` when reading a
committed file, including before loading a trusted joblib predictor. The regular
`predict_sessions` helper does this automatically. Checksums detect accidental
changes; they do not make untrusted pickle/joblib files safe to load.

Single-file writes use temporary files followed by atomic replacement. Interrupted
extraction, preprocessing and checkpoint writes retain the previous destination.
Do not replace these writers with direct writes to a published model file. Generation
retention is intentional; archive old run directories when storage needs it.

## Updating dependencies

Update `web/package-lock.json` with npm and verify the production build after a
Next.js update. Read the installed Next.js docs referenced by `web/AGENTS.md` before
changing framework code.

Regenerate the Python lock with uv 0.13.5:

```powershell
uv pip compile requirements.txt --python-version 3.14 --python-platform windows --output-file requirements.lock
```

Run the regression suite and a separate-output real-data smoke run after dependency
changes. Preserve earlier results instead of overwriting the incumbent model while
testing a new experiment.
