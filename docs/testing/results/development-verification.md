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

## Dataset-design checks

- `.venv-dev/Scripts/python.exe scripts/data/audit_raw_data.py --output data/reports/raw-dataset-profile.json`: passed across 70 raw files; the 1,000-row filtered sample satisfied its membership, balance, JSON, and privacy-field contract against the 248,522-row source.
- `.venv-dev/Scripts/python.exe scripts/data/build_central_profiles.py`: produced 1,000 schema-valid central profiles with 13,411 explicit structured claims and 21,407 evidence units.
- `.venv-dev/Scripts/python.exe scripts/data/build_concept_catalog.py`: produced 14,116 source-preserved concepts: 13,939 ESCO concepts and 177 O*NET concepts. Twenty-one semantically identical duplicate ESCO rows were collapsed by concept URI.
- `.venv-dev/Scripts/python.exe scripts/data/map_central_claims.py`: exactly mapped 2,065 of 13,411 claim instances (15.398%); 1,082 were ambiguous and 10,264 unmatched. Across 3,464 unique labels, 274 mapped exactly (7.910%).
- `.venv-dev/Scripts/python.exe scripts/data/build_occupation_benchmarks.py`: produced 4,055 source-preserved occupation benchmarks (3,039 unique ESCO occupations and 1,016 O*NET occupations) with 177,865 requirements. It retained 4,903 O*NET requirements as suppressed provenance with unavailable numeric ratings. Four semantically identical duplicate ESCO occupation rows were collapsed by concept URI.

Exact mapping measures lexical taxonomy coverage, not extractor accuracy, semantic equivalence, or proficiency. Ambiguous and unmatched claims are retained for review. The filtered-sample selection itself cannot yet be reproduced because its generator was not supplied.

## Independent annotation pilot preparation

The local packet builder produced 125 mapping tasks (50 ambiguous, 50 unmatched, 25 exact-match audit) and 50 profile-skill level tasks. The level tasks use 10 distinct profiles from each of five source groups; 25 have a direct skill mention in professional text and 25 require broader context review. Public task records contain no `profile_id`, `cohort`, `seniority`, `job_family`, `seed_role`, or `sample_group` fields. Two blank response templates were created per task type. `labels_assigned` is 0.

After adding a task-content digest check and one additional mapping-validation case, the final focused annotation and concept-mapping run passed all 11 tests. The documentation checker reported 0 errors, and `git diff --check` completed without whitespace errors. At that stage, no reviewer decisions or model-ready labels existed.

## AI pilot review, 2026-10-05

GPT-6 Sol Medium and Sol High independently answered the public synthetic pilot packets. The existing validator accepted both complete files. Initial agreement was 87/125 concept mappings (69.6%) and 48/50 per-skill evidence levels (96%). A blind GPT-6 Astra Low review then answered only the 38 mapping and 2 level disagreements; validation accepted all 40 answers. The two original disagreement queues remain saved locally, and separate three-model reconciliation reports record 125/125 mapping and 50/50 level decisions with no pending AI adjudications.

Astra's 38 mapping decisions matched Sol Medium in 25 cases, Sol High in 4, and neither in 9. Many disputes concerned a named product versus a broad software category. The rubric and [ADR 0013](../../adr/0013-specificity-in-concept-review.md) now make that distinction explicit for future human annotation. The AI files were produced under the earlier rubric and were not retroactively changed. They are pilot judgments on synthetic profiles, not independent human ground truth, representative performance estimates, or XGBoost training targets.

The blind dispute exporter produced task-only packets of 38 mapping and two level cases. Blank human adjudicator templates contain the same number of rows. A separate expanded synthetic batch contains 100 unlabelled profile-skill tasks, 20 per design group, with 50 direct and 50 indirect skill mentions and no overlap with the 50 pilot profiles. Two blank human reviewer templates contain 100 rows each. Public packets were checked for generation-label fields; none were present. This is a balanced synthetic design batch, not a representative sample of real users.

After these workflow changes, `.venv-dev/Scripts/python.exe -m pytest scripts/data/test_annotation_workflow.py scripts/data/test_concept_mapping.py -q` passed 14 tests. `scripts/check_docs.py` reported 0 errors and `git diff --check` reported no whitespace errors. The three-model reconciliation validator accepted every AI annotation. No human labels or model training results exist.

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
