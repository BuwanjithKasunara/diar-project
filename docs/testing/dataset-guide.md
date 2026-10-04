# Dataset guide

Development dataset version 1 contains [30 synthetic profiles](../../backend/tests/fixtures/profiles.json): two per career/visibility combination, using skills-only and public-contact variants. Labels identify skills, source states, required/forbidden rules, and sharing-compatible actions. [Six focused cases](../../backend/tests/fixtures/baseline.json) retain extraction outputs from revision `f2ef9730d32b22d23ae9572503c3bb63f2956722`.

Version 3 adds [the evidence-scoring evaluation set](../../backend/tests/fixtures/evaluation_v3.json) and [deterministic GitHub REST snapshots](../../backend/tests/fixtures/github_v3.json), each marked `dataset_version: 3.0`. All identities and repository content are synthetic or anonymised. The evaluation set covers natural-language expert-like evidence, novices, sparse profiles, archive-heavy accounts, keyword stuffing, trivial fresh repositories, unavailable sources, and expected capability states. The GitHub snapshots cover README/topic extraction, empty descriptions, older relevant repositories, pagination/selection, rate limits, missing READMEs, unknown languages, and Dockerfile mapping.

Run `python scripts/evaluate.py` to print the legacy regression metrics and version 3 gate metrics as JSON without writing files. Version 3 reports macro extraction precision/recall, strong-evidence retention, keyword-stuffing/trivial-repository resistance, insufficient-evidence handling, and absence-only recommendation safety. Baseline comparison applies only to the six focused cases; the 30-profile matrix has current labels/results but no captured historical baseline. Empty denominators produce null metrics. Never use private personal data in fixtures.

These authored regression cases cannot establish general accuracy. Final evaluation needs independently labelled held-out examples and annotation guidance. See [results](results/development-verification.md) for actual fixture provenance and measurements.

## External synthetic-profile design sample

The source [Synthetic US Candidate Profiles](https://huggingface.co/datasets/akzaidan/People) is stored as [`synthetic_profiles.parquet`](../../data/raw/synthetic_profiles/synthetic_profiles.parquet). Its dataset description identifies the profiles as synthetic and the dataset as MIT licensed. The source contains 248,522 rows.

The filtered design sample is [`synthetic_profiles_filtered.parquet`](../../data/raw/synthetic_profiles/synthetic_profiles_filtered.parquet). It contains 1,000 profiles: 200 each for software engineering, data science, research, product management, and entrepreneurial-adjacent roles. The first four groups use the source `job_family`; the entrepreneurial-adjacent group takes 40 profiles each from `business development manager`, `business operations manager`, `growth marketer`, `strategy consultant`, and `venture capital associate`. These are adjacent role labels, not a claim that the source contains founder profiles. Selection is deterministic (SHA-256 priority with seed `20261004`); the output adds a `sample_group` column.

The output omits the top-level country and removes nested age, ethnicity, legal-status, visa/sponsorship, desired-salary, and location fields, including work-location preferences. It also removes `experience_years` as a direct age proxy. Other role and capability evidence remains available. The original Parquet is not modified. This sample is for dataset design only; synthetic provenance and balanced role counts do not establish model validity or hiring suitability. See [ADR 0008](../adr/0008-privacy-filtered-candidate-sample.md).

## Raw-data audit

Install the development requirements, then run `python scripts/data/audit_raw_data.py --output data/reports/raw-dataset-profile.json` from the repository root. The command inventories the downloaded CSV, JSON-lines, Parquet, and text files without modifying them. It also verifies that the filtered profiles are unique source members, have the documented group and adjacent-role counts, contain valid profile JSON, and omit the prohibited privacy fields.

The audit does not prove that the documented SHA-256 selection procedure produced an existing sample, because the generator was not supplied with the downloaded files. Reproduction of the selection itself remains a separate provenance requirement; the audit verifies the resulting sample contract.

## Central evidence profiles

Run `python scripts/data/build_central_profiles.py` to convert the filtered synthetic design sample into schema-valid JSON Lines under `data/interim/`. The version 1 builder creates claims only from explicit structured skills. It retains selected professional descriptions as evidence but removes employer names, school names, dates, GPA, spoken languages, career interests, and source location/demographic fields. Synthetic cohort, job-family, seniority, seed-role, and sample-group values are isolated as design labels and explicitly excluded from model input.

The builder does not assign knowledge levels, infer concepts from free text, or compare profiles with benchmarks. Those are separate evaluated stages governed by [ADR 0009](../adr/0009-central-evidence-profile.md).

## Exact taxonomy mapping

Run `python scripts/data/build_concept_catalog.py`, followed by `python scripts/data/map_central_claims.py`. The first command creates source-preserved ESCO/O*NET concepts. The second maps explicit claims only when their case-folded, whitespace-normalized label exactly matches a preferred label or alias. It records single matches, ambiguous candidate sets, and unmatched claims separately. Inspect `data/reports/concept-mapping-v1.json` for observed coverage; coverage is a taxonomy-alignment measure, not model accuracy or proficiency evidence. See [ADR 0010](../adr/0010-exact-taxonomy-concept-mapping.md).

## Occupation benchmarks

Run `python scripts/data/build_occupation_benchmarks.py` after building the concept catalogue. The output stores ESCO and O*NET occupations separately. It preserves ESCO essential/optional relationships, O*NET importance/level values, source suppression and relevance flags, and software examples. It does not normalize the two taxonomies to a shared score. See [ADR 0011](../adr/0011-source-preserved-occupation-benchmarks.md).
