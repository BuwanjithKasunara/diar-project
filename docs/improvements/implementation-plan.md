# DIAR incremental improvements plan

Status: groups 1–4 merged; IDs 5–6 implemented and verified on branch, awaiting user commit/review/merge.
Prepared: 2026-10-08.
Repository: https://github.com/BuwanjithKasunara/diar-project
Working copy: `C:\Projects\diar\diar-project-main`.

## Purpose and decisions

Improve the existing FastAPI, plain JavaScript, SQLite, dictionary extraction,
fuzzy/rule scoring and TF-IDF/logistic-regression system through separate,
reviewable improvements. XGBoost and a replacement architecture are outside scope.
LinkedIn PDF import and automatic LinkedIn profile retrieval are excluded by the
user's decision; pasted LinkedIn text remains the supported input.

Implement improvement 9 before the report-history and recommendation-interface
improvements (5 and 6). Do not start with file scanning: input validation and
request responsiveness should come first, so new network work has safe bounds.
Finish extraction/evidence corrections before building additional presentation.
Minimal controls and evidence rendering necessary for improvement 9 belong to
that improvement; the broader UI improvements follow it.

## Starting state and implementation preflight

At preparation, the working copy is clean on `fix/privacy-report-controls`.
The earlier privacy realignment and summary UI are present locally. This is not
proof that the branch has merged; check origin before any implementation.
The prior scope scans public GitHub metadata and supplied text, not file contents.
See [the realignment record](../privacy/realignment.md) and
[its original plan](../privacy/implementation-plan.md) for that history.

Before each stage:

1. Read applicable repository instructions and this plan; confirm the working copy.
2. Check status, remotes, branch and current upstream merge state. Preserve user edits.
3. Start the group from updated main after the preceding PR has merged. Never
   silently stack an improvement on an unmerged branch.
4. Record the starting commit, actual branch and author in the delivery record.
5. Inspect current behavior again: this document records a code-review snapshot,
   not a guarantee that the implementation has stayed unchanged.

Creating this document does not authorize implementation, commit, push or merge.
The user requests each implementation stage separately and performs the provided
commit/push commands. Documentation can be committed with the current open PR;
application improvements use their own branches after that PR merges.

## Delivery order and attribution

IDs refer to the agreed nine-item list; execution order differs intentionally.
Each row is one branch/PR containing related improvements. The user's final
attribution split is four improvements for raveesha and five for charya; do not
alternate authors. IDs 1–4 belong to raveesha; IDs 5–9 belong to charya.

| Order | ID | Improvement | Proposed branch | Author | Status |
|---|---|---|---|---|---|
| 1 | 1, 2, 3 | Input validation and career evidence/extraction | `fix/analysis-evidence-foundation` | raveesha2002 | Merged in PR #6 (`1f25833`) |
| 2 | 7 | Failure recovery/responsiveness | `fix/analysis-request-recovery` | charya19 | Merged in PR #7 (`b7bc448`) |
| 3 | 9 | Public repository file privacy scan | `feat/repository-file-privacy` | charya19 | Merged in PR #8 (`bc95c03`) |
| 4 | 4 | ML uncertainty/explanations | `fix/ml-prediction-evidence` | raveesha2002 | Merged in PR #9 (`cb18bbe`) |
| 5 | 5, 6 | Saved report history/export and recommendation navigation | `feat/report-review-navigation` | charya19 | Implemented and verified; uncommitted |
| 6 | 8 | Reproducible setup/verification | `chore/reproducible-project-setup` | charya19 | Planned |

Group 1 starts from verified merged main commit `0839edd` (privacy PR #5).
Uncommitted planning documentation was carried into this group without discarding
it. Assignments describe authorship for user-run commands, not completed commits.
Each improvement retains its own delivery record even when sharing a PR.

Verified identities from the earlier project plan:

- `charya19 <309141509+charya19@users.noreply.github.com>`
- `raveesha2002 <208922648+raveesha2002@users.noreply.github.com>`

When a stage is ready, provide PowerShell commands listing its exact changed paths
and setting temporary committer name/email, with restoration in `finally`, and
explicit `--author`. GitHub push authentication is separate from commit attribution.
Push the stage branch, review its PR, merge, then update main before the next stage.
Additional corrections before merge go on the same stage branch.

## Compatibility rules

- Preserve existing report keys and rule identifiers where their meaning is unchanged.
  Add optional fields and defaults for old reports; do not rewrite historical rows.
- Keep privacy evidence, saved-report protection and career evaluation independent.
  Repository file text must not enter career skill extraction or ML inputs in stage 9.
- A privately submitted resume is application evidence, not public exposure.
  Supplied LinkedIn text does not prove actual audience or account settings.
- ID 2 may intentionally change weak-evidence advice; ID 3 may change skill
  matches; ID 4 may change ML outputs. Record these intended differences rather
  than promising identical results across all stages.
- Privacy stages must preserve career scores and predictions for the same career inputs.
- No external profile edits, repository changes, account deletions or visibility changes.
- Avoid database migrations unless a stage demonstrates why optional report JSON
  fields cannot meet its requirements. Never introduce one without recording its impact.
- Existing deployment lacks authentication/report ownership. History UI is for the
  local prototype. Shared public hosting requires separately planned access control.

## Stage specifications

### ID 1: Input and resume upload validation

Relevant files: `backend/app/main.py`, `backend/app/modules/extraction.py`,
`frontend/index.html`, request/extraction tests.

- Validate trimmed inputs at the API and frontend; require at least one usable source.
  A failed GitHub lookup with no other career data is handled as unavailable evidence,
  not a valid empty professional profile.
- Validate GitHub usernames without reflecting arbitrary untrusted input in errors.
- Establish documented constants: suggested PDF limit 5 MiB, 30 pages and supplied
  text limit 100,000 characters. Check existing reasonable examples before fixing
  these values; record final values and rationale.
- Bound upload reading, validate the actual PDF, handle encrypted/corrupt/empty files,
  and close PDF resources even when extraction fails. File extensions alone are not validation.
- Explain that scanned PDFs without a text layer require a text-based PDF or pasted
  alternative; OCR is outside this stage. Do not silently classify them as absent.
- Use clear 4xx responses for invalid input; preserve useful other sources where
  partial processing is supported and explicitly explain what was excluded.

Acceptance: empty/whitespace, invalid username, oversized, encrypted, malformed,
image-only and valid PDFs have explicit outcomes; invalid requests do not save a
misleading report. Valid existing sources still work.

### ID 2: Insufficient career evidence

Relevant files: extraction, identity construction, alignment and explanation modules.

- Separate source availability from evidence sufficiency and actual profile completeness.
  Pasted text length alone must not establish whether a LinkedIn account is complete.
- Phrase undetected skills as absent from supplied evidence, not proven lack of ability.
- Represent unavailable experience as unknown instead of automatically claiming zero.
  Consider LinkedIn experience only where supported by identifiable evidence.
- Restrict resume date heuristics to experience context; education dates should not
  become years of work experience. Do not add overlapping job durations blindly.
- Withhold unsupported career judgements; use additive status fields so historical
  numeric fields can remain readable without treating an unknown as a scored zero.
- Document which metrics/rules changed and preserve useful matches from partial sources.

Acceptance: missing resume, brief paste, useful partial text, education-only dates,
overlapping job periods and complete sources produce defensible advice. Privacy
findings from a short paste remain available independently of career sufficiency.

### ID 3: Skill context extraction

- Preserve sentence/line boundaries during normalization and bound negation,
  planned-learning and uncertainty to the relevant clause.
- Deduplicate overlapping aliases for the same occurrence before computing frequency.
- Retain supported aliases, typo tolerance and claimed/uncertain/planned/negated categories.
- Add focused fixtures for multiline lists, contrast clauses, abbreviations and
  repeated aliases. Store synthetic text, never real personal profiles, in fixtures.

Acceptance: denying Java on one line does not deny Python on another; learning
intent is distinguished from active experience; aliases do not inflate one mention.
Record intended changes to scores caused by corrected skill evidence.

### ID 7: Failure recovery and responsiveness

- Keep the last successful report available while a new request runs; restore/display
  it with a clear failed-attempt notice when the new request fails.
- Add frontend timeout/cancellation and stale-response guards. Document that aborting
  the browser request does not by itself guarantee cancellation of backend persistence.
- Move synchronous network/PDF/model work off the async event loop with the smallest
  suitable approach. Keep database sessions in their owning execution context;
  do not pass a SQLAlchemy session between worker threads.
- Establish request deadlines and predictable partial failures. Avoid automatic POST
  retries that might create duplicate reports. Keep health requests responsive.
- Handle model load/train failures as an unavailable ML component when rule analysis
  can still run. Coordinate final uncertainty semantics with ID 4.

Acceptance: timeout, failed API, rapid repeated requests and model failure produce
clear outcomes; previous reports remain usable; concurrent health requests are not
blocked by GitHub waits. Deletion errors and report-protection behavior still work.

### ID 9: Bounded public repository file privacy scanning

Purpose: extend metadata review to selected current public text files, before
broader report/recommendation UI work. Do not describe it as scanning an entire repository.

#### Collection scope and limits

- Offer an explicit optional control, off by default: review public README and
  supported text files. Existing metadata-only requests remain fast and compatible.
- Use only repositories already returned by the public listing. Include forks for
  exposure review; record the selected repository order and reasons for exclusions.
- Start with README plus root `CONTRIBUTING.md` and `SECURITY.md` when present.
  These are an allowlist, not a recursive source-code crawler. Wider content scanning
  requires a separately reviewed scope extension.
- Proposed hard limits: first 5 fetched repositories, at most 3 files per repository,
  100 KiB decoded text per file, 1 MiB aggregate decoded text, 25 additional HTTP
  requests, 5 seconds per request and a 20-second elapsed scan budget. Final values
  must be documented and tested; neither retries nor discovery can bypass budgets.
- Scan the default branch at a recorded commit SHA where practical. Resolve files
  through fixed GitHub API endpoints and repository metadata, not arbitrary URLs
  embedded in files. Never follow README links or submodules.
- Allow only public anonymous retrieval initially. Do not expand an authenticated
  token's access to private content. Exclude private repositories, binaries,
  symlinks, generated/vendor folders, archives, issues, PRs and commit-history text.
- Bound response reading and decoded size, handle unsupported encodings, and stop
  safely on rate limits/deadlines. Do not download large files and truncate afterwards.

#### Evidence and advice

- Reuse the four existing kinds: email, phone, street address and date of birth.
  Preserve possible-phone labels and avoid treating metrics/dates/versions as phones.
  API-key/password detection is outside this stage.
- Add a repository-file source with masked repository/path context, relative file
  path, line number, revision and masked excerpt; IDs must be unique and stable within
  the report. LinkedIn, public resume and metadata evidence still work as before.
- Scan with whole-text context where labels span lines, then map match offsets to
  lines. Do not lose masking across adjacent/overlapping values when cropping excerpts.
- Mask personal details in file paths and labels too. An optional GitHub source link
  must obey the selected handle/contact protection policy; omit it when a safe link
  cannot be constructed. Never leave an unredacted URL beside redacted evidence.
- Findings in public files are review candidates, not proof that contacts belong to
  the account owner or that a professional contact route is inappropriate. Preserve
  this uncertainty for sample, documentation and contributor contact details.
- Group advice by repository/file/kind where helpful and link the exact evidence.
  Suggest removing/replacing unnecessary information in that file. Do not advise
  making every repository private or claiming a file edit removes historical copies.
- Default collection/storage is masked evidence only; never persist raw downloaded
  files, including with report policy `none`. Retain transient raw text only as
  necessary for scanning and exclude it from logs/errors, career extraction and ML.

#### Coverage, failure isolation and compatibility

- Add optional file coverage fields: enabled flag, repository/file counts and statuses,
  revision information, skipped reasons and budget/timeout/rate-limit notices.
  Disabled, unavailable, partial and checked are different states.
- A missing README is not a clean privacy result. One failing file must not discard
  metadata evidence, other file findings or career analysis.
- Respect the evidence cap while still disclosing omitted findings and later-source
  coverage. Prevent file findings from silently consuming all evidence for other sources.
- Replace the old blanket "README files were not inspected" notice only when the
  optional scan ran; say exactly which files were checked and retain historical
  report limitations. History contents/settings/private repositories remain unchecked.
- Expose a minimal enable control and readable file evidence/coverage in this PR.
  Broad filters/history presentation are reserved for IDs 5 and 6.

Acceptance: mocked public files with each kind, multiline labels, contact-bearing
paths, examples, forks and clean text; disabled/missing/binary/oversized files;
one-file failure, rate limit, malicious URLs and all budget boundaries. Verify no
private retrieval or arbitrary URL requests, no raw persistence/logging, masked
create/read/export behavior, unchanged career/ML inputs, and readable old reports.
No live scan of a user's repositories is needed for automated tests.

Required decision record: `docs/privacy/repository-file-scanning.md` must describe
why this extends the original metadata-only scope, chosen limits, false positives,
revision/link masking, failure behavior, test evidence and remaining exclusions.
Update the realignment record without rewriting the original plan's historical scope.

### ID 4: ML uncertainty and explanations

- Identify empty/no-vocabulary input and provide an insufficient-evidence result.
  Any low-confidence/ambiguity threshold must be evaluated and documented, not guessed.
- The current keyword list is not a measured explanation. Either label it as matching
  vocabulary or implement deterministic ranked model contributions with a defensible method.
- Keep the TF-IDF/logistic-regression model. Do not call probabilities calibrated
  confidence or guaranteed correctness without evidence supporting that description.
- Handle missing/corrupt model, missing dataset and failed training consistently;
  preserve rule/benchmark analysis when ML is unavailable.
- Record relevant evaluation examples and the limits of applying training-data results
  to real profiles. No replacement model or XGBoost.

Acceptance: empty, irrelevant, ambiguous and strong role-specific input; stable
keyword ordering/explanations; model failure; target probability matches the returned
distribution. Old reports with the previous ML fields still render.

### ID 5: Saved report history and export

- Reuse existing list/get/delete APIs and protected responses for a local history panel.
  Reopen reports after refresh; communicate loading, empty, legacy and failure states.
- Export the report currently returned under its stored protection policy, initially
  as JSON and a readable print view if feasible. Do not fetch raw data to recreate it.
- Include benchmark, report time, evidence coverage/limits, file-scan status and
  protection policy. Do not imply exported copies disappear when a DIAR row is deleted.
- Keep input and reopened-report state distinct; prevent deletion/export of the wrong
  report during loading. Do not silently reanalyse a historical report with new rules.

Acceptance: reopen/delete/export current and historical reports; all policies;
failed requests; protected file paths/links; no unredacted leak in filenames/downloads.

### ID 6: Recommendation navigation

- Filter by career/privacy and priority, preserving the full list and rule evidence.
  Add a small suggested-first-steps area based on the existing ranking policy.
- Make repository-file privacy actions easy to find before long lists of career skills;
  avoid arbitrary new risk scores or promises that an action fixes all exposure.
- Maintain anchors from privacy cards to evidence and recommendations across filters.
  Reveal a target hidden by a filter rather than leaving a broken navigation experience.
- Use associated labels, keyboard controls and readable narrow-screen layouts.

Acceptance: mixed categories, empty filtered list, legacy uncategorized actions,
stable priority order, keyboard navigation and working evidence links at desktop/mobile widths.

### ID 8: Reproducible setup and verification

- Record a tested Python version and compatible runtime/development dependency versions.
  Verify a clean environment rather than copying incidental local packages blindly.
- Add GitHub Actions for the existing regression suite using mocked GitHub services
  and isolated databases. Tests must not depend on live profiles or download models.
- Record dataset source, licence/provenance where known, class counts, split/seed,
  duplicate/leakage checks and evaluation method. Mark unavailable provenance as unknown.
- Replace unsupported fixed accuracy claims with a dated reproducible evaluation
  record, including limits; commit metrics/configuration rather than personal data.
- Document model preparation, failure behavior and local startup. Keep the no-npm frontend.

Acceptance: a clean setup follows README successfully and CI reproduces relevant
checks; no external credentials required; evaluation claims trace to a saved record.

## Verification and documentation for every PR

Run focused meaningful checks for that change and the existing backend regression
suite before handoff. For interface changes, verify in the browser with synthetic
fixtures, including failed requests and a narrow viewport. Reuse checks that already
passed unless code changes or unresolved failures justify repetition.

Each PR must include:

1. Updated user instructions/limitations in README or the relevant feature document.
2. A delivery-record entry under this directory using the template below: problem,
   final behavior, intentional differences, touched components, compatibility,
   verification, limitations and rollback. Do not call planned work implemented.
3. Stage status updated to implemented on branch only after verification. Record
   merged status and merge commit only after checking the actual merge.
4. A self-contained PR description, actual changed paths and the user's commit/push
   commands. Record deviations from this plan and their rationale.

### Delivery record template

Create `docs/improvements/id-N-delivery.md` when implementing that stage:

```text
Improvement ID/title:
Status: implemented on branch / merged
Author, branch, starting commit, PR and merge commit (where verified):
Problem and prior behavior:
Final behavior and intended output changes:
Components/contracts affected:
Compatibility with existing/historical reports:
Verification commands, results and browser evidence:
Known limits and excluded scope:
Plan deviations and rationale:
Rollback approach and effect on reports already created:
```

## Rollback and stopping criteria

Before merge, correct the stage branch or leave the PR unmerged. After merge, prefer
a revert PR for its merge commit to preserve shared history. Check dependencies
before reverting earlier stages; later code may rely on additive fields/helpers.
Never reset or force-push shared main. Reverting code does not erase already saved
reports, exports, external information or previously downloaded copies.

Stop a stage's handoff when required checks fail, evidence would be overstated, or
the change expands collection outside its declared limits. Resolve it within that
stage or document a concrete user decision needed; do not silently proceed to the next.
