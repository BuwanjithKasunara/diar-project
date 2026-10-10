# ID 9: Public repository file privacy scanning

Status: implemented on `feat/repository-file-privacy`; awaiting user commit/review/merge.
Commit author: `charya19 <309141509+charya19@users.noreply.github.com>`.
Starting commit: `b7bc448` (verified merge of improvement 7 in PR #7).
This stage's implementation commit, PR and merge: pending.

## Problem, final behavior and components

Metadata-only privacy review missed supported personal information inside public
README files. The new optional scan adds masked root-file evidence, line/revision
context, source-specific review advice and explicit checked/skipped coverage.
It is off by default; request/byte/time bounds and anonymous fixed-endpoint transport
limit additional collection. File text never contributes to career/ML inputs.

Affected: new repository_privacy module, GitHub extraction integration, analysis
form/worker flag, evidence aggregation and advice labels, minimal frontend control
and evidence/coverage rendering. Existing response keys/legacy reports remain
readable; a new source and optional file-coverage field extend the report JSON.
No database migration, account setting change or external file edit is performed.

## Decisions, limitations and plan deviations

See [the decision record](../privacy/repository-file-scanning.md) for all final limits,
API choices, ownership uncertainty and historical-copy exclusions. The first scope
is root files only; nested README/source content needs a separate extension.
Source links are deliberately omitted to avoid introducing an unmasked handle or
contact URL into protected evidence. This satisfies the plan's optional-link choice.
Minimal opt-in/evidence UI is required now; broader UI work remains scheduled later.

Model/score invariance applies to the same career inputs. The scan can add privacy
recommendations and take more time; an overall backend deadline still limits the
entire analysis. It is not a whole-repository audit or secret scanner.

## Verification

Command: `..\.venv\Scripts\python.exe -m pytest tests -q` from `backend`.
Final result: **191 passed**, three existing FastAPI/Starlette deprecation warnings,
2026-10-09. This includes 34 new file-scan cases. `git diff --check` passed.
Synthetic fixtures cover four detail types, multiline labels/line numbers, forks,
private/malformed identifiers, safe path construction/ignored URLs, symlink/submodule
exclusion, binary/unsupported encodings, missing/oversized files, truncated trees,
response/request/decoded-byte/elapsed bounds, rate limits, partial file failure,
masked labels, finding caps and existing-source preservation.
Create/read/storage checks cover all saved-report policies and invariant career
scores/ML text. Export UI is still planned; these checks validate the protected JSON
that a later export feature must reuse, not an existing download feature.

Browser fixtures run the actual application/scanner/frontend with synthetic GitHub
responses, synthetic ML and an in-memory database. No real repositories are fetched.
Verified default-disabled coverage, enabled findings for all four detail types,
masked excerpts, source lines/revision, working recommendation/evidence anchors and
missing README/allowlisted files as `no_supported_files`/`not_found`. Final enabled
coverage no longer carries a contradictory metadata-only exclusion. No console
errors appeared; a 390-pixel viewport had document width 375 with no horizontal
overflow. Local synthetic preview: `C:\Projects\diar\backups\repository-file-privacy-preview.png`
(outside the repository). The temporary server was stopped after checks.

## Rollback

Revert this group after checking later dependencies. Report JSON is additive and
historical rows are not rewritten; no database migration is needed. Previously
saved masked findings remain as the original report's evidence, even after rollback.
