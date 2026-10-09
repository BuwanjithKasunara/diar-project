# ID 1: Input and resume validation

Status: merged from `fix/analysis-evidence-foundation` in PR #6 (`1f25833`).
Author for commit commands: raveesha2002.
Starting commit: `0839edd`; implementation commit: `91f9962`.

## Problem and final behavior

Empty submissions previously generated reports; uploads were read without a bound,
and PDFs with no readable text looked like absent sources. API and form now validate
nonempty inputs and GitHub username syntax. Limits are 5 MiB per PDF, 30 pages,
100,000 extracted PDF characters and 100,000 LinkedIn characters. These limits are
conservative prototype defaults, not measured capacity claims.

Invalid inputs return 400; size/text limits return 413. A failed GitHub-only lookup
returns 422 without saving a report; other supplied sources remain usable when GitHub
fails. PDF parsing closes resources and distinguishes encrypted, empty/image-only,
oversized and invalid documents. Invalid uploads reject the submission even when
other inputs were supplied, so the user can correct or remove the file explicitly.

Affected: main.py, extraction.py, frontend form and synthetic regression fixtures.
Existing saved rows and response structures remain readable.

## Verification and limits

See `id-2-delivery.md` for shared group verification results. Fixtures include valid
PDF, encrypted/empty/malformed PDFs, size/page limits, invalid/empty inputs and
GitHub failure with/without fallback text. PDFs are generated locally.

No OCR is provided. Username validation is syntactic, not proof the account exists.
The multipart parser may spool an upload before application validation; this is an
application processing bound, not a reverse-proxy request-body limit.

## Rollback

Revert the group PR after checking dependent groups. Invalid requests create no
reports; reverting code does not remove previously saved reports. No database migration.
