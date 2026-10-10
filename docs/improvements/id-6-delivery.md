# ID 6: Recommendation navigation

Status: implemented and verified on `feat/report-review-navigation`; uncommitted.
Author: `charya19 <309141509+charya19@users.noreply.github.com>`.
Starting commit: `cb18bbe8231c181c91be95def4ff2ccfbde66b88` (PR #9 merge).
PR/implementation commit: pending user commands. IDs 5 and 6 share one PR.

Final behavior: Category and priority filters preserve original ordering/ranks. First steps use the first three existing ranked actions; public repository file actions get shortcuts. Hidden targets are revealed before navigation and evidence links point to recorded evidence. New career actions get an additive career category; existing visibility categories map to privacy in the UI and uncategorized historical actions remain legacy.

Previously reports could not be reopened or exported through the interface and
recommendations were a long unfiltered list. Inputs remain separate from report
state. Loading blocks conflicting open/export/delete/analysis operations; failed
opens keep the prior report. GET requests have a 15-second timeout and history
refreshes suppress stale responses. POST retries are not introduced.

Compatibility: existing list/get/delete APIs and protected responses are reused.
No raw data retrieval, reanalysis, migration or historical row rewrite. JSON
exports preserve the full returned report, including protection/coverage/limits.
Filename is fixed plus numeric ID. Older uncategorized actions remain available.
Print temporarily resets filters then restores them after printing.

Verification, 2026-10-11: `..\.venv\Scripts\python.exe -m pytest tests -q` from backend: 199 passed, three existing deprecation warnings; `git diff --check` passed.
Browser preview uses actual API/frontend with an isolated in-memory database,
synthetic profiles and unavailable synthetic ML; no user rows or live GitHub
were used. Reopening after reload, all three stored policies, download contents,
privacy/legacy/empty filters, hidden-action revealing, deletion/history refresh,
loading-disabled controls and no console errors checked. A loaded report at a
390px viewport measured client/scroll width 375/375. Initial network failure
showed a history error. Native print dialog/PDF rendering was not verified.

Limits: latest 50 only; no ownership/authentication (local prototype).
Deleting a row cannot delete exported copies or historical public content.
Plan deviations: additive creation timestamp and career category were necessary
for metadata display/filtering; timestamp bypass applies only to server time.
Rollback: revert this stage commit after checking dependencies; saved rows remain
readable and optional fields require no data cleanup.
