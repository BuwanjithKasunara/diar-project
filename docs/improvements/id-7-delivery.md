# ID 7: Analysis failure recovery and responsiveness

Status: implemented on `fix/analysis-request-recovery`; awaiting user commit/review/merge.
Commit author: `charya19 <309141509+charya19@users.noreply.github.com>`.
Starting commit: `1f25833`, verified merge of the preceding group in PR #6.
This group's commit, PR and merge: pending.

## Problem and resulting behavior

Starting another analysis previously erased the displayed successful report, and
synchronous PDF/GitHub/model work blocked the async analysis endpoint's event loop.
The form now retains the previous report during processing and after a failure,
shows whether it is still the previous result, and provides Cancel analysis.
Submission/deletion guards prevent duplicate submissions and deleting the displayed
old report while a new analysis is running. Request IDs prevent a cancelled or older
response from overwriting a newer result; analysis POSTs are never automatically retried.

The browser stops waiting after 45 seconds. Cancellation/network-timeout messages
explain that the server may still finish and save a report. Check the saved-report
API before retrying if avoiding duplicates is important; history UI is still planned.
Only a received backend 504 guarantees this timed-out analysis did not save a report.

The API reads/closes the bounded upload asynchronously and runs PDF extraction,
GitHub calls, skill/identity construction, model prediction, rules and report
protection in an AnyIO worker. Only source values go into the worker; the report DB
session is not passed to it. Persistence remains in the route after successful
construction. The worker has a 40-second deadline including worker queue time,
starting after upload read/validation. Deadline expiry returns 504, abandons waiting
for the worker and skips persistence, even if its calculation later completes.
The existing GitHub request timeouts and partial-evidence behavior are retained.

Unexpected ML load/train/prediction errors now produce an unavailable prediction
while retaining rule-based analysis. The new fallback logs the exception class,
not the raw exception/source text. A model lock serializes lazy model loading and
training to avoid concurrent requests writing the same artifact. ID 4 will refine
ML uncertainty; this stage only isolates failures.

## Affected contracts and compatibility

Components: main.py, ml_classifier.py, frontend/index.html, requirements.txt and tests.
AnyIO becomes an explicit dependency (already used transitively by FastAPI).
Reports and scoring remain compatible; new fallback uses existing ML output fields.
No database migration, raw-file persistence or external-platform modifications.
Legacy report protection, report reads/deletion and privacy evidence remain supported.

## Verification

Backend: `..\.venv\Scripts\python.exe -m pytest tests -q` from `backend`:
**157 passed**, three existing deprecation warnings, 2026-10-08.
New tests block a worker with events and verify health responds independently;
shorten the deadline and verify no row before/after late worker completion;
exercise a model exception while preserving rules and excluding its raw text;
check no DB session is sent into construction. Existing privacy/validation suites pass.

Browser: actual application/frontend, synthetic GitHub/ML, in-memory report database.
Successful analysis followed by HTTP 503 retains the first report. Slow analysis
disables report deletion; cancelling retains the prior report; a subsequent successful
request displays its own report, with the late cancelled result ignored.
No console errors were observed; at a 390-pixel viewport the document width was
375 pixels, with no horizontal overflow. A synthetic failure preview is saved at
`C:\Projects\diar\backups\analysis-recovery-preview.png` outside the repository.
The temporary preview server was stopped after verification. Browser timeout
duration is implemented but not exercised by waiting the full 45 seconds in this
preview; backend deadline and manual cancellation were exercised separately.

## Limits and design decisions

Cancellation is not server-side job cancellation or idempotency. A request can
persist after the browser aborts, or its successful response can be lost in transit.
No polling/background-job system is introduced. The backend construction deadline
does not cover multipart upload reception or final DB persistence. Short SQLite
writes remain on the route; this does not establish a throughput guarantee.
Abandoned workers finish their current operation; Python threads are not forcibly
killed. Model initialization may finish and populate the cache after a deadline,
but it cannot save a report. Thread capacity is finite under heavy concurrent load.

## Rollback

Revert this group after checking the subsequent file-scan dependency. No migration
or data rewrite is needed; saved reports retain their original data. Rollback does
not remove rows saved after a browser cancellation or exported copies.
