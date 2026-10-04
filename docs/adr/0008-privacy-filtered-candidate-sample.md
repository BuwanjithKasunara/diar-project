# 0008: Privacy-filtered synthetic candidate sample

Date: 2026-10-04  
Status: Accepted

## Context

The 248,522-row synthetic candidate source is larger than needed for initial DIAR dataset design and contains fields that are unnecessary for capability evidence and could introduce harmful bias. The design sample also needs representation across the requested role areas.

## Decision

Keep the downloaded source unchanged and create a separate, deterministic 1,000-row Parquet sample with 200 profiles per group: software engineering, data science, research, product management, and entrepreneurial-adjacent roles. The first four groups use the corresponding source `job_family`. Entrepreneurial-adjacent coverage is limited to source roles `business development manager`, `business operations manager`, `growth marketer`, `strategy consultant`, and `venture capital associate`, with 40 profiles per role; these labels are not treated as founder profiles. Selection uses SHA-256 priorities with seed `20261004`.

Exclude the top-level country and nested age, ethnicity, legal-status, visa/sponsorship, salary, and location fields, including work-location preferences. Also exclude `experience_years` as a direct age proxy. Add `sample_group` to the filtered file so the sampling stratum is explicit.

## Alternatives

- Use the full source: unnecessary size for early dataset design and retains disallowed fields.
- Take an unstratified random sample: it may underrepresent less common role families.
- Label product or executive roles as founders: unsupported by the source role labels.

## Consequences

The smaller sample is balanced and repeatable while leaving the source intact. It is suitable for dataset design, not for claims of model accuracy, hiring suitability, or representation of founder profiles. The source's synthetic and licensing statements come from its dataset description and are not independently verified here.

## Related documents

- [Dataset guide](../testing/dataset-guide.md)
- [Filtered sample](../../data/raw/synthetic_profiles/synthetic_profiles_filtered.parquet)
