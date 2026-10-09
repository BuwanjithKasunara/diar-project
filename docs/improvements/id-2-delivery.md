# ID 2: Conservative career evidence interpretation

Status: merged from `fix/analysis-evidence-foundation` in PR #6 (`1f25833`).
Author for commit commands: raveesha2002.
Starting commit: `0839edd`; implementation commit: `91f9962`.

## Problem and final behavior

Weak inputs previously led to missing-skill and zero-experience advice. No supported
skill mentions now adds `skill_evidence_status=insufficient_evidence` and withholds
skill-gap rules. Numeric metrics remain for API compatibility, but the UI and narrative
withhold alignment judgements. Benchmark lists still identify undetected skills;
the UI does not display them as established gaps without skill evidence.

Useful partial text contributes skill evidence. Undetected skills are described as
gaps in supplied information, not proof of lacking ability. Contact-only text can
still yield privacy findings independently. Certifications advice is withheld when
the consolidated profile has no meaningful career evidence.

`experience_evidence` records years/status/basis. Unknown is represented by null in
that new structure, while the legacy numeric estimate remains zero for compatibility.
Experience rules consult the new status and do not interpret unknown as zero years.
Explicit totals or year ranges within a labelled experience section can support an
estimate. Education dates are excluded; overlapping periods are merged. Across resume
and LinkedIn the maximum supported estimate is used, never the sum of duplicate totals.

Completeness presentation now describes supplied source coverage, not verified account
completeness. The existing coverage formula still depends on source states and length
heuristics; it is not a quality assessment of a LinkedIn account.

Affected: extraction, identity construction, alignment, explanation and minimal report
presentation. Existing report keys, privacy provenance and saved protection remain.
Legacy reports without evidence status continue to render their prior scores.

## Verification

Backend command: `..\.venv\Scripts\python.exe -m pytest tests -q` from `backend`.
Final result: **153 passed**, with three existing FastAPI/Starlette deprecation
warnings, on 2026-10-08. Focused new fixtures: 24 passed within that suite.
`git diff --check` passed. An initial new test used an oversized parameter as its
test ID, exceeding Windows temporary-path limits; named IDs corrected the test
harness before the final passing run.

Browser verification used the actual app and frontend with synthetic ML/GitHub
responses and an in-memory database. Empty submission showed validation; contact-only
text showed withheld alignment plus a masked phone finding; useful partial text
showed Python claimed, Java negated and planned learning. No console errors appeared.
The 390-pixel viewport had no horizontal overflow. The learning-verb false match
found in the browser was corrected and verified by a new backend regression case.
Local preview: `C:\Projects\diar\backups\analysis-foundation-preview.png` (outside
the repository; synthetic data). The temporary server was stopped after checks.
New fixtures cover unknown experience, education dates, overlaps, future dates,
LinkedIn evidence, contact-only privacy and independent skill context.

## Limits and deviations

No comprehensive employment parser: month-level dates, career breaks and unusual
section headings may remain unknown. Year-only estimates are approximate. Conflicting
source totals use the larger estimate and require user review. Claimed skills remain
self-reported, not independently verified competence. Minimal UI wording/status
changes belong to this foundation; broader UI work still follows file scanning.

## Rollback

Revert the group PR after checking dependencies. Additive report JSON fields require
no migration; historical reports are not rescored or rewritten. Old consumers must
consult new status fields to distinguish unknown values from legacy numeric zero.
