# ID 4: ML uncertainty and explanations

Status: implemented and verified on `fix/ml-prediction-evidence`; uncommitted.
Author: `raveesha2002 <208922648+raveesha2002@users.noreply.github.com>`.
Starting commit: `bc95c0376f3714b0a561cb361f9bfba6d38a7f23` (PR #8 merged).

Empty or zero-vocabulary text previously produced misleading model availability
or a prior-based role. It now returns `prediction_status: insufficient_evidence`,
no role distribution and no target match. Load, training and inference failures
return `unavailable`, allowing rule analysis to continue.

Probabilities are labelled model probabilities, never calibrated confidence or
confirmation of ability. The legacy `confidence` numeric key is preserved.
Target lookup is case-insensitive and uses the returned rounded distribution;
unrecognized targets return null rather than an invented zero probability.
Matching unigram/bigram vocabulary is ranked by TF-IDF weight with alphabetical
ties; it is explicitly not presented as measured class contributions.

No arbitrary confidence cutoff was introduced. Synthetic role-specific and mixed
examples verify behavior, not accuracy or calibration on real profiles. Mixed
inputs still receive a model ranking with a limitation notice. Selecting an
abstention threshold needs representative labelled validation data and is deferred.
TF-IDF/logistic regression remains unchanged; no model replacement or migration.
Older reports lacking the new fields still render with a probability limitation.
Saved historical JSON is not rewritten. Privacy collection remains unchanged.

Verification, 2026-10-11: `..\.venv\Scripts\python.exe -m pytest tests -q`
from backend: 198 passed, three pre-existing deprecation warnings. Seven focused
synthetic cases cover empty/unmatched, mixed/strong text, deterministic vocabulary,
target/distribution agreement and failed/corrupt models. Existing pipeline test
covers the shipped model and rule-preserving failure behavior.
Browser checked actual rendering functions with insufficient, predicted, legacy
and unavailable synthetic ML data: labels and notices rendered, no console errors.
Static preview intentionally had no live backend (API offline); full live browser
analysis was not performed. Temporary fixture removed. `git diff --check` passed.

Touched components: classifier, explanation narrative, ML panel, README and plan.
Rollback: revert the eventual stage commit; existing optional JSON fields remain
readable. No saved report data needs modification.
