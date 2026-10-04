# Verification record

Date: 2026-10-04. Base revision: `f2ef9730d32b22d23ae9572503c3bb63f2956722`; redesign changes are an uncommitted working tree. Dataset versions: the original focused and 30-profile fixtures plus the version 3 anonymised evidence-scoring and GitHub snapshot fixtures.

## Documentation checks executed

- `.venv-dev/Scripts/python.exe scripts/check_docs.py`: passed with 0 errors.
- `.venv-dev/Scripts/python.exe -m unittest discover -s scripts -p test_check_docs.py -v`: 3 tests passed. Temporary fixtures cover valid, encoded, external, and missing links plus duplicate ADR numbers.

The checker validates local target existence, not heading fragments, remote URLs, or factual correctness of prose.

## Automated application checks

- `.venv-dev/Scripts/python.exe -m pytest backend/tests -q`: 81 tests passed; one third-party Starlette `TestClient` deprecation warning was emitted.
- `.venv-dev/Scripts/python.exe -m compileall -q backend/app scripts`: passed.
- `node --check frontend/app.js`: passed.
- `git diff --check`: passed; Git reported only line-ending conversion warnings.

The version 3 tests cover capability-group alternatives and isolation, evidence strengths and provenance, Q-learning assertion handling, deterministic repository and README selection, partial and rate-limited GitHub scans, language whitelisting and Dockerfile mapping, raw recency observations, absence-only recommendation safety, legacy compatibility, and version 3 persistence. Existing extraction, planner, PDF, API validation, privacy, and explicit report-management regressions remain covered.

## Evaluation results

Command: `.venv-dev/Scripts/python.exe scripts/evaluate.py`.

- Original focused six-case corrected extractor: micro precision 1.000, micro recall 1.000, exact-case accuracy 6/6.
- Original authored 30-profile matrix: micro precision 1.000, micro recall 1.000, exact-case accuracy 30/30.
- Version 3 evidence set: macro precision 1.000, macro recall 0.967; micro precision 1.000, micro recall 0.929; exact-case accuracy 9/10.
- Strong-evidence cases avoiding limited outcomes: 100%.
- Keyword-stuffed or trivial-repository cases avoiding broad evidence coverage: 100%.
- Insufficient-evidence cases returning only `not_assessed`: 100%.
- Absence-only cases producing confirmed-gap wording: 0%.

All version 3 acceptance gates passed. The one non-exact extraction case omitted two expected concepts from indirect wording (`evaluated` and `retrieval system`) without inventing false positives. These figures establish regression behaviour on authored, anonymised synthetic cases, not generalisation to a real population.

## Browser and responsive checks

The FastAPI service and static frontend were run on loopback addresses with an isolated temporary database. The embedded browser-control transport was unavailable, so the installed Edge browser was driven headlessly through its local DevTools interface by `scripts/verify_browser_v3.mjs`.

A synthetic LinkedIn-text workflow exercised analysis, rendering, explicit saving, history, and legacy opening. At a 1280 by 900 viewport it displayed all six AI Engineer capability groups, 15 rendered provenance records, the neutral benchmark/source/recency observations, and collapsed method details. The rendered result contained none of the old `inactive`, skill-match, source-coverage, or moderate-grade terminology. All controls were labelled and no duplicate element IDs were detected.

An accepted version 2 fixture was saved and reopened from history. It displayed `Historical heuristic—not recalculated`, kept historical grades collapsed, and offered a new-analysis action. At a 375 by 812 viewport the input form and results remained visible with no horizontal overflow. A browser screenshot was successfully captured in memory. No JavaScript console errors or failed network loads occurred during the verified workflow.

## Remaining verification limits

GitHub behaviour is verified with deterministic snapshots; an optional live GitHub smoke test was not run. The evaluation set is authored rather than held out or population representative. OCR for scanned PDFs remains deliberately out of scope. Broader independent profiles and user testing remain future work. Relative planner costs and catalogue coverage are documented assumptions rather than time estimates or evidence of competence.
