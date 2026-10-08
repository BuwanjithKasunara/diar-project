# DIAR privacy feature realignment plan

Status: implementation plan only. No application changes are authorized by this document itself.

Project: `C:\Projects\diar\diar-project-main`
Origin: `https://github.com/BuwanjithKasunara/diar-project`
Prepared: 2026-10-08
Planning recommendation: GPT-6.1 Sol, High effort.
Implementation: GPT-6.1 Sol, Low effort, one checked stage at a time; use High effort for final review or an unresolved design conflict.

## 1. Intended outcome

The visibility choice expresses the user's desired online presence. The system reviews available evidence and recommends actions the user can take on their own public profiles and repositories. It must preserve useful professional qualifications and distinguish public exposure from private job-application information.

Privacy Focused means reduce unnecessary exposure while retaining a useful professional identity. Semi-Public means maintain a selective professional presence. Fully Public means develop an intentional professional presence while still reviewing unnecessary sensitive disclosures.

Report redaction and deletion are separate controls for information stored by DIAR. They do not reduce information already visible on GitHub or LinkedIn. The report must explain that distinction without suggesting DIAR has changed an external profile.

## 2. Verified starting state and recovery approach

At planning time, the local branch is `fix/report-privacy`; its HEAD is `b47aa89`, the merge of improvement 2. There are uncommitted edits to README.md, main.py, alignment_engine.py and frontend/index.html, plus new privacy.py and test_privacy.py. These are the incorrectly framed improvement 3. The original main also already conflated visibility preferences with report masking and had only one generic contact-exposure rule.

Before implementation:

1. Read applicable AGENTS.md files, this plan, Git status, remotes and recent history. Confirm the exact project path; do not use the older sibling `C:\Projects\diar\diar-project`.
2. Fetch origin and check whether improvement 3 has since been committed, pushed or merged. Do not assume this snapshot is still current.
3. Preserve all existing user work. Save the current tracked diff and copies of the two untracked files in a timestamped folder outside the repository. A plain `git diff` does not include untracked files. Record the branch and starting commit in that folder.
4. If improvement 3 remains unmerged, correct its existing branch and PR. If it has merged, start a correction branch such as `fix/privacy-presence-recommendations` from current origin/main, using a suitable isolated worktree if local changes prevent a safe switch.
5. Do not use reset --hard, force push, delete a branch, discard files or rewrite shared history to obtain a clean starting point.

Treat this as a three-part correction to improvement 3, using separate sequential branches/PRs and the requested attribution: Part 1 sda2003, Part 2 raveesha2002, Part 3 charya19. Do not start the next part until the previous PR has merged and the new main has been fetched. When each part is ready, provide explicit PowerShell commit/push commands with that part's actual changed paths and the established temporary committer-environment pattern. Verified attribution: `sda2003 <172163628+sda2003@users.noreply.github.com>`, `raveesha2002 <208922648+raveesha2002@users.noreply.github.com>`, and `charya19 <309141509+charya19@users.noreply.github.com>`. Push authentication is separate from commit attribution.

## 3. Constraints that protect working behavior

- Keep the existing FastAPI, plain JavaScript frontend, SQLite and rule engine architecture. No XGBoost, new model, background crawler or platform write integration.
- Keep benchmark data, skill extraction semantics, fuzzy calculations, career score formulas, ML training and predictions unchanged.
- Keep improvement 1's readable recommendation labels and argument preservation, and improvement 2's independent GitHub requests and incomplete-evidence safeguards.
- Keep existing top-level report keys and recommendation fields. Extend JSON structures with optional fields rather than rename existing response fields.
- Keep Fully Public career recommendations equivalent when there is no exposure finding. Change other modes only where advice would contradict the chosen visibility goal.
- Keep source availability, source coverage and privacy coverage separate. A short LinkedIn paste may contain a detectable phone even if career evidence is partial; a successful GitHub repository fetch still does not prove file contents were inspected.
- Use additive JSON metadata in report_json. No database column migration is required for this scope.
- Never publish, privatize, edit or delete an external profile/repository automatically.
- No destructive migration of historical reports and no extra collection of raw source text for persistence.

## 4. Initial scope and explicit limitations

The first implementation analyzes data already available through the current workflow:

| Source | What can be reviewed | Evidence about public exposure |
|---|---|---|
| GitHub profile | Bio and public email/location/blog fields returned by the existing profile request | Observed in a public API response; state exactly which field was inspected |
| GitHub repositories | Names, descriptions and topics for every repository in the fetched page, including forks | Public repository metadata; identify the repository and field |
| LinkedIn | Entire pasted text, not just its first-line headline | User-supplied text; actual profile audience and current settings are unknown |
| Resume | Entire extracted PDF text | Job-application document by default; not evidence of public exposure |

GitHub career analysis can continue excluding forks. Privacy review must not inherit that exclusion: a fork's public description can contain personal information too. Privacy review must run before reducing repositories to the five top_repos in the report.

Preserve the current bounded repository request, its limit of 100 and its warning behavior. The initial implementation does not fetch README files, source files, commit history, issues or private repositories. It also cannot inspect GitHub email-hiding settings or LinkedIn audience settings. Include these exclusions in the coverage description. Future README/file scanning would be a separate project decision with request limits and its own failure handling; it is not required for this correction.

## 5. Behavior of the three visibility goals

| Goal | Exposure advice | Career/presence advice |
|---|---|---|
| Fully Public | Review detected phone, precise address and other unnecessary personal details; review whether a public email is an appropriate professional contact | Existing professional portfolio advice may remain, without encouraging disclosure of personal details |
| Semi-Public | Recommend limiting unnecessary personal fields and reviewing the audience for the affected information | Recommend a selected public portfolio and share other evidence directly with recruiters/collaborators |
| Privacy Focused | Prioritize removing or restricting unnecessary publicly visible personal details and reviewing linked personal pages | Offer private projects, selective sharing and a minimal useful professional profile; do not demand additional public repositories |

Names, qualifications, employer names, education, programming skills, project names, dates and follower counts are not privacy violations merely because they occur in a profile. Do not equate a high repository count with dangerous exposure. Do not recommend deleting accounts, deleting career history, or privatizing every repository by default.

A work email may be intentionally public. Do not infer that an email is personal from its domain. Phrase email recommendations as a review of whether that address should be public, with an optional professional contact channel.

## 6. Resume and LinkedIn context

Resume contact details remain useful for recruitment. Their presence alone must not produce a public-exposure recommendation or lower any score.

Add an optional boolean form field `resume_publicly_shared`, default false. Display a small checkbox near the upload: "This resume is also publicly available online." If checked, findings can explain that exposure is based on the user's declaration; DIAR has not verified the public copy. If unchecked, scan it for context but treat standard contact details as job-application information. Do not show the raw contact values in the report.

LinkedIn findings must say "Detected in the LinkedIn text you supplied" and make audience advice conditional: "If this is visible to everyone, remove it or restrict its audience." Do not say DIAR verified public exposure or checked account settings. No additional audience selector is required in the initial scope.

If only a resume is supplied and it is not declared public, return "Public profile exposure was not assessed" rather than "No privacy risks found." If sources fail or are missing, report their missing coverage without treating absence as success.

## 7. Evidence design and detection rules

Create a focused `backend/app/modules/privacy_assessment.py` module for exposure evidence and recommendations. Keep report sanitization in privacy.py. Avoid a general refactor of extraction.py or alignment_engine.py.

Proposed entry points:

- `scan_text_for_exposure(text, source, location, exposure_status, evidence_prefix)` returns findings from one field/text body without changing that text.
- `collect_privacy_evidence(resume_text, linkedin_text, github_privacy_data, resume_publicly_shared=False)` returns findings and coverage.
- `assess_visibility(privacy_evidence, visibility_level)` returns human-readable findings and rule candidates compatible with the current recommendation engine.

Exposure status values: `observed_public`, `supplied_text_unknown_audience`, `user_declared_public`, `application_document`. These describe provenance, not numerical confidence.

Each evidence item contains:

```json
{
  "id": "github-repo-1-phone",
  "source": "github_repository",
  "location": "description",
  "repository_name": "portfolio-demo",
  "kind": "phone",
  "exposure_status": "observed_public",
  "display_evidence": "Contact: [PHONE]",
  "recommendation_eligible": true
}
```

Allow repository URLs only from the returned GitHub metadata and only if they identify the relevant public repository; do not invent a URL or fetch its destination. No raw contact value belongs in display_evidence, an ID, recommendation text, test snapshots, report history, logging or error messages. Keep enough context to locate the issue: platform, repository name, field or a bounded masked text excerpt.

Initial detectors:

1. Email addresses: medium-priority review of an intentionally public contact channel.
2. Phone numbers: high-priority review for public or user-declared public sources; conditional review for pasted LinkedIn text. Use conservative digit/format boundaries and skip dates, year ranges, plausible metric strings, versions and identifier/code contexts when distinguishable. Ambiguous matches become "possible phone number" findings, not asserted facts.
3. Detailed street address: high-priority review only with clear context such as an address label and a house/street component. A city/country/location field alone is not an exact-address finding. Ambiguous locations are not flagged automatically.
4. Date of birth: review only with explicit DOB/date-of-birth labeling. Career date ranges and dates alone are not flagged.

Use contextual labels for the last two detectors, bounded matching and documented supported formats. If conservative address/DOB detection cannot pass the specified false-positive checks, ship contact detection with a clear coverage exclusion rather than broaden a regex until it fires. Do not add government-ID, password/secret, face/photo or semantic personal-information classifiers in this correction.

Deduplicate the same kind/value within one source/location in memory. If retaining a comparison key is useful, keep it transient; do not persist raw matches or reusable hashes of personal data. Separate exposure on GitHub and LinkedIn into distinct findings because the user must act in different places. Cap persisted findings (for example 50) and masked excerpt length (for example 160 characters); disclose omitted counts. Detection can continue counting after the display cap.

## 8. Collection and pipeline integration

In extraction.py, use the existing GitHub responses to construct a separate `privacy_data` result containing per-field findings and privacy coverage. Scan all fetched repository metadata before it is summarized. Do not append contacts to combined ML text, change skill inputs, or keep extra copies of raw response objects in the saved profile.

GitHub profile-request failure must not prevent analysis of a supplied resume/LinkedIn paste. Repository-request failure must preserve profile findings. Limited repository coverage must retain findings from the fetched page and state that the remainder was not checked. Empty repositories with a successful response mean metadata was checked for zero repositories, not that all account privacy settings were checked.

In main.py, assemble privacy evidence from the original source text before report sanitization, then attach bounded masked evidence/coverage to the profile or pass it explicitly to alignment. Pick one ownership path and use it consistently; prefer `profile['privacy_evidence']` so run_alignment retains its current signature.

Replace the combined-input boolean scan introduced in improvement 3. Replace identity_construction.py's experience-snippet/headline-only detector as the source of truth. Keep `public_contact_info_detected` for compatibility, but derive it only from eligible contact findings marked observed_public or user_declared_public. Document that unknown-audience LinkedIn findings are separate review candidates, not verified public contacts. Do not let this legacy flag alone generate new recommendations.

The order is: extract career data and exposure evidence -> construct profile -> run existing ML and scoring -> assess visibility and contextualize conflicting actions -> rank recommendations -> build explanation -> apply independent report protection -> persist -> return.

## 9. Report contract and action generation

Retain `visibility_assessment.selected_level`, `public_contact_info_detected` and string-list `findings`. Add optional fields:

```json
{
  "assessment_version": 2,
  "goal": "reduce_unnecessary_public_exposure",
  "evidence": [],
  "coverage": {
    "github_profile": {"status": "checked", "checked_fields": ["bio", "email", "location", "blog"]},
    "github_repositories": {"status": "limited", "repositories_checked": 100},
    "linkedin": {"status": "supplied_text_only", "audience_verified": false},
    "resume": {"status": "application_document"}
  },
  "limitations": ["Repository files and platform audience settings were not inspected."]
}
```

Coverage states should come from actual operations (`not_supplied`, `failed`, `checked`, `limited`, `supplied_text_only`, `application_document`, `user_declared_public`) rather than text length alone. Include fields actually returned/inspected; absence of a profile field should not be represented as a finding about that information.

Group actionable evidence by source and kind. Examples: "Review the phone number in your GitHub bio", "Review contact details in repository descriptions", "Review the audience for contact details in your LinkedIn text". Each recommendation must identify where to act and why, with masked evidence IDs. Do not claim that report masking already solved the issue.

Add source-specific action keys and readable labels to recommendation_engine.py. Because it deduplicates by action string, use distinct arguments such as `review_contact_exposure:GitHub profile` and `review_contact_exposure:LinkedIn text`; otherwise separate sources would collapse into one generic action. Group affected repositories in the reason/evidence list rather than emit an unbounded rule per repository.

Keep rank, priority, recommendation, rule_id and explanation. Optionally carry `category` (career/visibility), `source`, `evidence_ids` and `suggested_steps` through the engine. Preserve the existing priority queue and insertion-order tie behavior. Avoid a wholesale sorting change.

Reuse the R10 family for version-2 privacy rules, with explicit source/kind suffixes. Retain old labels/rule compatibility for stored reports; historical recommendations are snapshots and are not regenerated on read.

## 10. Prevent conflicting career advice

Compute original career metrics first. Adapt action candidates, not the numeric scores, for the selected visibility goal.

| Existing candidate | Fully Public | Semi-Public | Privacy Focused |
|---|---|---|---|
| Build more public portfolio repositories (R4) | Preserve existing advice | Develop portfolio work and choose selected projects to showcase | Develop private portfolio work and share selected evidence directly |
| Increase activity / refresh stale repos (R5) | Preserve | Keep selected showcased projects current | Keep relevant work current; public commit activity is optional |
| Diversify projects/languages (R6) | Preserve | Preserve technical learning without requiring all projects public | Preserve technical learning; private projects are valid |
| Missing LinkedIn text (R9) | Request existing text for analysis; do not infer absence of an account | Request relevant text; a limited profile is acceptable | Optional source request, without demanding creation/expansion of a public profile |
| Maximize profile completeness (R11) | Keep only as an explicit professional-presence action; supplied-source completeness does not prove online completeness | No unconditional expansion instruction | No unconditional expansion instruction |

Implement these changes narrowly where the rules are constructed or through a small explicit action mapping. Do not suppress skill, experience or certification advice. Missing evidence notices must still appear. Do not change the definition of source-state metrics to make Privacy Focused users score better or worse.

For Privacy Focused, explain that career evidence completeness/activity are career indicators, not measurements of privacy safety. A user may intentionally keep work private. The system cannot infer why repositories are absent or how much private work exists.

## 11. Independent protection of saved reports

Keep whole-report masking and report deletion as useful storage features, but remove the implication that the online visibility goal is their configuration.

Add optional form field `report_redaction` with explicit values `mask_contacts` (default for new requests), `mask_contacts_and_handle`, `none`. Present it separately as "Saved report protection" with plain descriptions. No selection means the documented default; it must not silently derive a new policy from Privacy Focused.

Add `report_metadata` to report_json with a version and effective report_redaction policy. No new SQLite column is needed. Report analysis and rankings are computed before redaction and must be identical across all three report policies. Evidence excerpts are always masked, even when none is selected, because the evidence contract never stores raw contact matches.

privacy.py should expose an explicit-policy sanitizer for production calls. The old `sanitize_profile_for_visibility` wrapper can remain for compatibility with old callers/tests, but new analysis must use the independent policy. Preserve date/numeric values and the technical vocabulary/username boundary safeguards.

For legacy rows lacking report_metadata, use the old policy mapping ONLY for their display/storage compatibility: Fully Public -> none; Semi-Public -> mask_contacts; Privacy Focused -> mask_contacts_and_handle. Do not relabel their old findings as version-2 exposure analysis. Do not reconstruct raw values already removed from a saved report.

GET report and history must use the effective stored policy, not just the current visibility goal. With handle masking, metadata and report payload must agree. Keep DELETE semantics (204 on successful deletion, 404 for unknown IDs); explain that deletion affects DIAR's saved copy, not external profiles or backups.

## 12. Frontend and explanation changes

Keep the existing layout and result sections. Rename "Preferred Visibility Level" to "Desired online presence" while retaining the three backend enum values. Explain each goal near the selector. Add the optional public-resume checkbox and separate saved-report protection selector.

The visibility result section must show actionable findings, where the information occurred, its provenance and coverage limits. Keep a concise positive statement for checked data with no finding: "No supported exposure patterns found in the inspected fields." Never say the account is safe/private or a full privacy audit passed.

Render masked evidence and source text with text nodes using the existing el helper. Do not insert source-derived HTML through innerHTML or create arbitrary clickable links from pasted text.

explainable_ai.py should summarize detected exposure, recommended actions and unavailable coverage separately from storage masking. Keep existing skill, fuzzy, source-state and ML narrative content. Avoid stating that credentials are shared, private settings were verified, or external information was removed.

Old report JSON may lack all new fields. Frontend rendering must fall back to the old findings list and label legacy analysis if report retrieval is exposed. Keep report deletion confirmation, cancellation and failure behavior intact.

README should describe the three goals, supported exposure types, source provenance, bounded repository scope, resume treatment, independent storage controls and the local API's existing access limitations. Update API form-field documentation. No claims of automated LinkedIn scraping or full repository-file inspection.

## 13. File map for the implementer

| File | Intended change |
|---|---|
| backend/app/modules/privacy_assessment.py (new) | Conservative detectors, masked evidence, source coverage and goal-based privacy rule candidates |
| backend/app/modules/extraction.py | Build privacy evidence from GitHub response fields/all fetched metadata without changing career extraction |
| backend/app/modules/identity_construction.py | Remove the old narrow detector as production truth; attach evidence and derive legacy contact flag |
| backend/app/modules/alignment_engine.py | Integrate privacy assessment and adapt contradictory public-presence actions while preserving score formulas |
| backend/app/modules/recommendation_engine.py | New readable action labels and optional evidence/category metadata; retain ranking/dedup semantics |
| backend/app/modules/explainable_ai.py | Accurate source/coverage and action narrative, separate from report redaction |
| backend/app/modules/privacy.py | Explicit independent report policy, legacy compatibility |
| backend/app/main.py | New optional fields, orchestration, report metadata and historical policy fallback |
| backend/app/schemas.py | Reflect optional response additions if schemas are used; do not impose a response model that strips existing keys |
| frontend/index.html | Goal explanations, source evidence, optional public-resume context, separate saved-report protection |
| README.md | Correct behavior, limitations, API additions and storage documentation |
| backend/tests/ | Detector, rule, pipeline, persistence and compatibility coverage described below |

Do not edit benchmarks.json, skills_dictionary.json, fuzzy_logic.py, ml_classifier.py, the career dataset, train_ml_model.py or requirements.txt unless an actual blocker is demonstrated and discussed. This plan does not require changes to them.

## 14. Implementation stages and gates

1. **Baseline and preservation.** Record working Git state, preserve edits/untracked files and run the existing suite. At plan time, the prior full-suite result was 57 passed with three deprecation warnings; it has not been rerun for this planning task. Existing tests include temporary-database fixtures; reuse them. Do not treat the current baseline as proof the intended privacy behavior is correct.
2. **Evidence collection.** Add privacy_assessment.py and GitHub evidence collection, with tests for source attribution, masked excerpts and false positives. Keep API/report behavior unchanged at this stage. Gate: existing career extraction and GitHub failure/limit tests remain valid.
3. **Rules and conflicts.** Add source-aware privacy rules and the narrow visibility-goal adaptations. Gate: career scores/ML outputs remain invariant, rules identify actual evidence, resume-only contact does not trigger public-exposure advice, no Privacy Focused recommendation demands more public presence.
4. **Pipeline and report compatibility.** Integrate full input evidence, explicit report_redaction, report_metadata, public-resume context and legacy reads. Gate: new create/read/history/deletion flows and old reports work in an isolated database without losing stored rows.
5. **UI, explanations and docs.** Connect controls, evidence and coverage notices, preserve original layout, update README. Gate: browser verification of all three goals, privacy contexts, old/new response shapes and delete cancellation/error/success flows using disposable fixtures.
6. **Final review and handoff.** Run the full suite once after the final changes, inspect diff scope and verify no generated databases/models/source payloads are staged. Use High effort to review conflicts and compatibility. Provide summary, limitations, exact commit/push code and PR title/body. The user creates/merges the PR according to the existing workflow.

These stages map to the three separately merged parts in Section 19. Do not combine their commits or begin a dependent part before its preceding PR is merged. They are not authorization to make unrelated improvements or silently start the other numbered improvements.

## 15. Required verification matrix

Use synthetic source data and mocked GitHub responses; tests must not call live GitHub or use real personal information. API tests use isolated temporary SQLite databases, never the user's saved-report database.

**Detection and context**

- Email and representative supported phone formats in GitHub bio, public email field and every fetched repository description/topic are detected.
- A contact in repository number 6 or 100 is not missed because top_repos only contains five; a fork's exposed metadata is included in privacy review without changing career repo counts.
- A contact near the end of pasted LinkedIn text is detected; advice remains conditional because the audience is unknown.
- Resume header contact with public checkbox false creates no public-exposure recommendation; checkbox true creates a user-declared-public review finding. Skill extraction, experience and ML inputs remain unchanged.
- Dates, year ranges, software versions, repository counts, star counts, ordinary cities and valid career achievements do not become asserted phone/address/DOB exposure findings. Long/nonnormal input is bounded and ambiguous cases are identified conservatively.
- Repeated contacts deduplicate within a location; separate platform actions survive recommendation deduplication. Empty data, finding/excerpt caps and null profile fields work.
- Masked evidence IDs, excerpts, recommendations, exceptions and persisted exposure-evidence objects do not contain raw detected contact values. Other extracted profile text follows the independently selected report_redaction policy; selecting none deliberately retains that extracted text.

**Rules and working features**

- Exercise all three goals with the same career evidence: benchmark comparison, gap scores, source-state metrics and ML results are unchanged, except documented wording/action adaptations.
- Fully Public without exposure preserves existing career rule ordering and readable labels.
- Semi-Public/Privacy Focused advice offers selective/private alternatives while keeping skill/experience/certification actions and missing-data notices.
- Contact findings do not change benchmark match scores. Unknown/missing sources do not produce an all-clear privacy claim.
- Valid GitHub profile + failed repo request retains profile exposure findings; limited coverage retains subset findings and warns; failed profile still permits supplied-text analysis.
- All existing recommendation argument, GitHub error/coverage, NLP polarity, scoring and ML tests continue to pass without weakening assertions just to obtain a green suite.

Existing privacy tests encode the former mode-to-redaction mapping. Preserve tests of that mapping for legacy compatibility wrappers/old rows, but rewrite new-analysis API cases to select report_redaction explicitly. Add cases proving the new default and independence from visibility goals. This is an intentional contract correction; do not delete masking/date/username-boundary/persistence assertions or relax unrelated regressions.

**Report protection and compatibility**

- All nine visibility-goal/report-redaction combinations give identical analysis with the same inputs, differing only in saved/displayed text according to the independent policy.
- Omitted new form fields use safe documented defaults; invalid policy strings return a clear 400 without saving a row.
- New report create/GET/history policy consistency, handle masking, all nested sections, numeric/date preservation and no mutation of input objects.
- Legacy rows with no new metadata stay readable; old privacy findings remain legacy findings; no raw data is restored or database row silently rewritten.
- Delete removes only the selected row; second deletion/unknown ID is 404; confirmation cancellation retains the report; UI errors keep the report visible and allow retry.

**Browser verification**

- Resume-only, public GitHub contact, LinkedIn unknown audience, unavailable repositories and clean inspected fields display the correct provenance/coverage.
- Goal selector and storage selector behave independently; the public-resume checkbox affects only exposure interpretation.
- Skills, benchmark scores, ML section and recommendations still render; no console errors or unsafe source HTML.
- Keyboard access and readable labels for new controls; ordinary desktop/mobile widths do not break the existing layout.

Database deletion is verified with API tests against temporary synthetic reports. Browser confirmation/cancellation can be checked without deleting anything. For browser success/error presentation, use a synthetic fixture endpoint that returns the chosen outcome without permanently deleting user data. Do not perform irreversible UI deletion of the user's existing reports as part of verification.

If sandbox restrictions prevent an existing ML/test/preview command from completing, use the normal approval mechanism rather than alter application behavior to bypass the restriction. Stop fixture servers after browser verification.

## 16. Acceptance examples

1. **Private application resume:** A PDF says "Python engineer; email person@example.com; phone +94 77 123 4567." No public sources are supplied and public-resume checkbox is false. The system gives career advice and says public exposure was not assessed. It does not recommend removing essential resume contact details.
2. **Public GitHub contact:** A fetched repository description contains a phone number. Privacy Focused recommends reviewing/removing that number from that named description and keeping a professional contact route if needed. The report shows a masked excerpt. It does not tell the user to delete the repository.
3. **LinkedIn uncertainty:** Pasted text includes an address. The system identifies the relevant text, says audience is unknown, and recommends restricting/removing unnecessary address detail if it is publicly visible. It does not claim to have checked LinkedIn settings.
4. **Limited fetch:** 100 repositories were fetched and more exist. Findings from those repositories are useful, but the report says the remaining repositories and all file contents were not inspected. Existing portfolio-count/activity recommendations remain withheld.
5. **No exposure finding:** Checked GitHub metadata has no supported pattern. The finding is limited to those fields, with no promise that the complete account is private or safe.
6. **Privacy career conflict:** Low public repository count can still appear in career metrics, but the action offers private portfolio work and selective sharing instead of demanding more public repositories.

## 17. Rollback and completion record

Before merge, rollback uses the preserved starting files or a separate corrective commit after inspecting the diff; never replace unrelated user work. After merge, revert the correction commit(s) or merge commit through a new branch/PR, choosing the right operation for the actual merge strategy. Do not erase shared Git history.

Keep the JSON/database changes additive so the old application can ignore extra metadata. Do not change table definitions, overwrite old reports, regenerate recommendations on reads or retrain models as part of rollback.

At handoff record: base commit, branch, exact changed files, passed/failed checks, supported detector formats, remaining coverage limitations, legacy behavior and PR text. No model/effort setting guarantees absence of regressions; the stage gates and explicit acceptance examples are the safeguards.

Typical verification commands, to run during implementation rather than during plan creation:

```powershell
Set-Location "C:\Projects\diar\diar-project-main\backend"
..\.venv\Scripts\python.exe -m pytest tests -q
Set-Location "C:\Projects\diar\diar-project-main"
git diff --check
git status --short
```

For stage-specific verification, run the relevant test file first. Broaden to the full suite at integration/final-review gates, or when a failure justifies it. Do not repeatedly rerun unchanged passing checks.

## 18. Instruction for the later Low-effort implementation

Read this whole plan before edits. Recheck its starting-state assumptions. Implement only the privacy correction described here, following stages 1-6 sequentially and keeping the existing project architecture. Use the file map, evidence contract, policy matrix and acceptance examples as the specification. Preserve existing work and the author/branch workflow. Do not infer public exposure from a private resume or unknown platform settings. Do not weaken working tests, change career scoring/ML, fetch arbitrary source links or implement a full repository crawler. If new evidence requires a material design change, explain the conflict before expanding scope. Leave commit/push to the user and provide exact commands when implementation is complete.

## 19. Three-PR / three-commit decomposition

Each part produces one focused commit on its own branch and one PR into `main`. The user commits/pushes and creates/merges each PR. After each merge, fetch `origin/main` and create the next branch from that updated main. Never stack a later branch on an unmerged predecessor; this keeps every PR independently reviewable and avoids replacing main. The worktree must be clean or safely preserved at each transition.

### Part 1 — Privacy evidence foundation

- **Branch:** `feat/privacy-evidence-foundation`
- **Commit author:** sda2003 / Sithum Alwis / `172163628+sda2003@users.noreply.github.com`
- **Purpose:** Add conservative, source-aware privacy evidence collection without changing recommendations, report redaction, career metrics or UI behavior yet.
- **Scope:** Add `backend/app/modules/privacy_assessment.py`; add focused GitHub profile/repository metadata collection in extraction.py, scanning all fetched repo metadata (including forks) before the top-five summary; include source/location/type, observed-vs-unknown provenance, bounded masked excerpts and per-source coverage. Add the optional `resume_publicly_shared=False` form input plumbing only if it can be accepted and recorded without changing current API outputs; otherwise defer its API/UI connection to Part 2. Keep this first PR strictly additive. Do not store raw contact values.
- **Committed documentation:** Add docs/README.md, docs/privacy/realignment.md and a repository copy of this implementation plan. Record the requirement mismatch, its known scope, evidence rather than assumptions about impact, the corrected design, staged delivery, validation and rollback. Link documentation from the main README. Update the record in Parts 2 and 3 rather than leave a final-looking document for an incomplete implementation.
- **Tests:** Unit cases for detectors, dates/versions/metric false positives, per-source attribution, masking, forks, repository 6 and 100, bounded findings, and GitHub profile/repo failures/limited pages. Existing API responses and career results remain unchanged.
- **Gate:** Full existing suite passes; new evidence is not exposed in the user-facing API unless an additive, documented evidence field is safe for old clients.

### Part 2 — Visibility rules and actionable recommendations

- **Branch:** `feat/privacy-recommendations`
- **Commit author:** raveesha2002 / `208922648+raveesha2002@users.noreply.github.com`
- **Purpose:** Connect the evidence foundation to visibility assessments and recommendations that tell the user what to review and where.
- **Scope:** Integrate evidence with profile construction/alignment, source-specific rule IDs and readable recommendation labels, masked evidence/coverage in the API response, and explainable summaries. Add the public-resume declaration control/API behavior. Adapt conflicting repo-count, activity, language and LinkedIn expansion actions by visibility goal while preserving benchmark scores, career skill advice, source-state safeguards, ML input and classifier results. Keep report persistence/redaction behavior unchanged in this PR; its existing policy remains temporarily compatible until Part 3.
- **Tests:** Acceptance examples 1–6; same career evidence yields same career scores and ML outputs across visibility goals; resume-only contact defaults to no public exposure recommendation; unknown-audience LinkedIn advice is conditional; source coverage failures never produce an all-clear; no Privacy Focused action demands increased public output.
- **Gate:** Full existing and new tests pass. Review the actual API response for legacy compatibility before the PR is opened.

### Part 3 — Independent saved-report protection and user interface

- **Branch:** `fix/privacy-report-controls`
- **Commit author:** charya19 / `309141509+charya19@users.noreply.github.com`
- **Purpose:** Separate the user's public-presence goal from the protection of DIAR's saved report, then make evidence and controls understandable in the UI and documentation.
- **Scope:** Integrate or refine privacy.py's whole-report sanitizer, independent optional `report_redaction` policy and additive report metadata; preserve a legacy fallback for old rows; keep report deletion; update frontend goal descriptions, optional public-resume control if deferred, separate saved-report selector, evidence/coverage rendering, confirmation/cancel/error states; update README. Do not add a database schema migration or change already saved rows.
- **Tests:** All nine visibility-goal/report-policy combinations; create/read/history consistency; default and invalid policy handling; legacy report compatibility; delete API behavior in isolated temporary SQLite; UI cancellation/error/synthetic-success checks; browser render for all goals and source states; no console errors.
- **Gate:** Full suite and planned browser checks pass; old reports render; git diff contains no generated database/model or real user data. The user reviews and merges this PR before improvement 4 begins.

### Handling the already prepared improvement 3 changes

At the plan's preparation snapshot, the current local `fix/report-privacy` branch contains uncommitted changes implementing redaction and deletion. Those changes were made before this corrected three-part breakdown. Preserve their full tracked diff and untracked files before moving branches. Do not commit the mixed branch as Part 1. Reuse deletion and report-redaction code/tests in Part 3 after Parts 1 and 2 merge, adjusting it to the independent `report_redaction` design. Reuse README changes only in Part 3. Keep any useful tests and run them against the final policy matrix. If the branch has since been committed or pushed, inspect its exact state first and use a new corrective branch/PR to avoid overwriting or rewriting shared history.

This replaces the earlier single-PR assumption. The three authorship assignments are explicitly set for this privacy realignment: sda2003, then raveesha2002, then charya19. It applies only to these three parts; continue to respect the user's later branch/author instructions for subsequent improvements.
