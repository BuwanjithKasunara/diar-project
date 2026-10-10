# ID 8: Reproducible setup and verification

Status: implemented and verified on `chore/reproducible-project-setup`; uncommitted.
Author: `charya19 <309141509+charya19@users.noreply.github.com>`.
Starting commit: `0995ec332c5e6b0c9461dd184bebf1a47432b3e0` (PR #10).
Implementation commit and PR: pending user commands.

Previously requirements were unpinned, tests could use the default report database,
and README claimed fixed 97%+ accuracy without a dated record. Direct runtime and
development requirements now have explicit versions and a full lock file records
a fresh Python 3.12.10 resolution. Uvicorn's optional standard extras are omitted:
the basic server meets startup needs and avoids platform-dependent optional packages.
Colorama is Windows-only in the lock. The no-npm frontend remains unchanged.

GitHub Actions installs the lock, runs pip check, the regression suite and offline
model evaluation on main pushes/PRs. Test defaults use temporary SQLite databases,
block real requests HTTP, and place trained artifacts in temporary storage.
Specialized fixtures still use their own isolated stores/mocks. No credentials or
external model downloads are needed after installing packages.

The evaluation CLI now records seed, split indices, input SHA-256, class counts,
package versions, duplicates, character near-duplicate screening, holdout metrics
and five shuffled stratified folds with TF-IDF fitted per fold. Evaluation does not
replace the model by default; `--save-model` explicitly retrains/saves the artifact.
The CSV is unchanged. Source/collection/consent/licence are unknown. See the dated
[dataset record](../testing/model-evaluation.md) and JSON for results and limitations.
No real-profile accuracy, calibration or abstention threshold is established.

Verification on 2026-10-11: fresh `.venv-repro` created and installed using
`python -m pip install -r backend/requirements-dev.txt`; generated lock resolved
only those dependencies. Lock installation checked with `--no-index` after install;
`pip check` passed. Fresh environment `python -m pytest tests -q` from backend:
199 passed, three existing deprecation warnings. Test temp storage required shell
escalation on this host; the successful run used isolated test databases.
`python train_ml_model.py` completed: 75 unique rows, 15 per class, zero exact
and screened holdout near duplicates, 100% holdout accuracy, 98.67% mean CV accuracy.
Fresh app startup and health/benchmark endpoints passed with isolated in-memory
storage. `git diff --check` passed. GitHub-hosted Ubuntu workflow has not run yet;
platform wheel resolution and that remote result remain pending until push.

Compatibility: production response/scoring, privacy scan and historical reports
are unchanged; the training CLI now requires explicit model-saving intent.
No data migration. Development dependencies moved out of runtime requirements.
README documents the lock installation, startup, evaluation and model failure path.
No original dataset license or provenance was invented.

Rollback: revert the stage commit; existing report rows and local model remain
usable. Environment installations/evaluation exports are local artifacts and are
not removed by a code revert. No deployment, push or merge was performed.
