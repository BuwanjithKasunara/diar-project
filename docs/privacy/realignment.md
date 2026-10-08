# Privacy requirement realignment record

Recorded: 2026-10-08. Starting main: `b47aa89` (merged improvement 2).

## Requirement and development mismatch

The intended Privacy Focused feature helps users reduce unnecessary information exposed
through their online presence. It should identify review candidates in available GitHub
profile/repository data and supplied LinkedIn text, explain where they occur, and suggest
actions on those sources while preserving useful professional qualifications.

The existing implementation treated the visibility preference partly as a setting for
masking the generated report. It had one generic contact-exposure rule, with a detector
limited to a resume experience snippet and LinkedIn headline. It did not distinguish a
private job-application resume from public information. Portfolio recommendations could
also encourage more public repositories or a fuller LinkedIn profile under Privacy Focused.

During improvement 3, additional report masking and deletion were prepared under the same
interpretation. The user clarified the requirement before those local changes were
committed or merged in the inspected checkout. That work was preserved for later reuse
as an independent saved-report feature. The assistant's interpretation carried the
requirement mismatch into that proposed improvement.

This is a requirement/implementation mismatch, not a recorded security breach. The review
establishes the behavior of the code; it does not establish that user data was disclosed or
that deployed instances were affected.

## Why it matters

- Masking a DIAR report does not remove information from GitHub or LinkedIn.
- Resume contact details are often necessary for recruitment and do not prove public exposure.
- A generic recommendation cannot tell the user which platform or field needs attention.
- Career recommendations that demand more public output can conflict with the user's goal.
- Missing data or a limited scan must not be presented as proof that the whole account is private.

## Agreed correction

Separate online-presence goals from DIAR's report-protection controls. Collect masked
evidence with source, field/repository, disclosure type, provenance and scan coverage.
Connect that evidence to specific rule-based advice in Part 2. Adapt contradictory career
actions without changing career scores, skill extraction, the ML classifier or its training.
Connect the independent saved-report controls and updated interface in Part 3.

Desired goals:

| Goal | Intended advice |
|---|---|
| Fully Public | Develop a professional presence while reviewing unnecessary personal disclosures |
| Semi-Public | Showcase selected professional evidence and limit unnecessary personal information |
| Privacy Focused | Reduce unnecessary public exposure and offer private/selective portfolio alternatives |

Public GitHub metadata is observed public evidence. Pasted LinkedIn text has an unknown
audience. A resume defaults to application information; an optional future declaration
can indicate that it is publicly shared, without claiming DIAR verified the public copy.
An email is a review candidate, not proof that it is a personal address or a vulnerability.

## Delivery and status

| Part | Author | Branch | Status |
|---|---|---|---|
| 1: Evidence foundation and development record | sda2003 | feat/privacy-evidence-foundation | Prepared for review; not committed/merged by the agent |
| 2: Visibility rules and source-specific advice | raveesha2002 | feat/privacy-recommendations | Planned; starts after Part 1 merges |
| 3: Independent report controls, interface and final docs | charya19 | fix/privacy-report-controls | Planned; starts after Part 2 merges |

Part 1 adds an internal evidence collector and uses the existing GitHub responses to scan
metadata. Its new findings are not yet connected to the analysis endpoint's report,
recommendation rules or interface. The existing user-facing privacy behavior remains until
the following parts are implemented. It should not be advertised as a completed privacy correction.

Before starting Part 1, the previous uncommitted improvement 3 files were copied outside
the repo and preserved in a named Git stash. The backup is local recovery material, not
part of the project commit. Shared Git history was not rewritten.

## Part 1 evidence contract and limits

The internal GitHub extraction result gains `privacy_data`. It contains `evidence`,
`findings_count`, `omitted_findings_count`, `coverage`, `supported_kinds` and `limitations`.
The evidence contains masked snippets and source-generated IDs, never raw matched values
or hashes of them. Findings are capped at 50; counts disclose omitted findings. Excerpts
are capped at 160 characters. Repeated values deduplicate within one field, while distinct
locations remain separate. Repository names in evidence are also masked when they contain
supported contact patterns.

Supported review candidates:

- Email patterns; no inference about personal versus business use.
- Phone-like numbers containing 7–15 digits. Labels such as phone/mobile/tel strengthen the
  interpretation; other matches remain explicitly `possible`. Labelled metrics/IDs,
  dotted versions and supported date/year-range patterns are excluded.
- A labelled street address containing a house/street component, or that same structural
  pattern in the returned GitHub location field. A city or country alone is not flagged.
- Explicit DOB/date-of-birth/birth-date labels followed by valid ISO dates or numeric
  day/month/year dates. Ordinary career dates alone are not flagged.

These are conservative, format-limited patterns; ambiguous data and unusual formats can
be missed or need review. There is no ML privacy classifier or universal sensitive-data detector.

GitHub review covers returned bio/email/location/blog fields and name/description/topics
for every repository in the existing fetched page, including forks. Career repository
counts continue excluding forks. The fetch remains limited to 100 repositories and makes
no extra requests. Profile findings survive repository-request failure. Partial repository
coverage is labelled limited; failed and not-supplied sources are distinct.

README files, source files, commit history, issues, private repositories and account
visibility settings are not inspected. A successful metadata scan is not a complete
account review. Supplied LinkedIn text is scanned in full by the collector, without
fetching a profile or verifying its audience. Resume text is similarly available to the
collector but defaults to `application_document` and is ineligible for exposure advice.

## Verification and prevention of recurrence

Part 1 tests use synthetic text, mocked network responses and isolated report databases.
They verify conservative patterns, redacted evidence, source context, coverage/failure
states, forks, findings outside the five-repository summary, output caps and unchanged
career extraction/API persistence. The complete Part 1 suite passed 96 tests on
2026-10-08 using `python -m pytest tests -q` from backend, with three existing dependency/
FastAPI deprecation warnings. Record the final test result in the PR; a passing suite
does not mean Part 2 or Part 3 has shipped.

Each subsequent part must update this status table and document its behavior, tests and
remaining limits. The detailed plan contains acceptance examples and the protected file
map. Keep source provenance in review discussions: "present in supplied text" and
"observed publicly" are different claims. Preserve a private-application-resume regression
case, goal-independent scoring checks and incomplete-coverage checks.

## Rollback

Use a corrective/revert commit or PR appropriate to the actual merge strategy. Preserve
unrelated work and keep the report schema additive. Do not erase shared history, rewrite
old reports, retrain the model or change database tables as part of this correction.

The [implementation plan](implementation-plan.md) is the specification for later parts.
