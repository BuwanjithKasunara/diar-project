# 0009: Source-neutral central evidence profile

Date: 2026-10-04  
Status: Accepted

## Context

DIAR receives heterogeneous candidate evidence from résumés, LinkedIn text, GitHub, and design datasets. Comparing each source independently with every benchmark would duplicate scoring logic and could make a missing source resemble missing ability. ESCO and O*NET are taxonomies, while SkillSpan contains annotated text spans; none of those rows represents a candidate.

The synthetic source also contains generation labels and fields such as employers, schools, dates, GPA, and spoken languages that are unnecessary for initial professional-capability extraction and may create privacy or shortcut-learning risks.

## Decision

Introduce central evidence profile schema `1.0.0`. Candidate sources first become source records, explicit claims, and provenance-bearing evidence units. Benchmark comparison will consume this single profile representation rather than compare each source separately.

Only explicit structured skills become claims during the current deterministic conversion. Free text remains evidence for a later semantic-extraction stage and is not interpreted by this builder. Canonical concept identifiers remain null until taxonomy mapping is implemented.

Keep source generation metadata under `design_labels` with `excluded_from_model_input=true`. Exclude employer and school names, dates, GPA, spoken languages, country/location, and demographic fields from the central profile. ESCO and O*NET will populate a separate concept/benchmark catalogue. SkillSpan will be used only for extractor development and evaluation, preserving its upstream splits.

## Alternatives

- Concatenate every dataset into one table: rows have incompatible meanings and would create invalid labels.
- Score each input source independently: duplicates comparison logic and confounds evidence availability with capability.
- Infer knowledge levels from synthetic seniority or cohort: those are generation labels, not independently verified knowledge labels.
- Extract semantic claims from free text now: this would mix deterministic normalization with an unevaluated extraction model.

## Consequences

All later extractors can target one contract, and benchmark scoring can remain source-neutral. Source provenance remains traceable. The additional conversion stage must be versioned and tested. The central profiles still contain professional free text and therefore remain sensitive local artifacts. A separately labelled outcome dataset is still required before XGBoost experimentation.

## Related documents

- [Central profile schema](../../data/schema/central-profile-v1.schema.json)
- [Source mappings](../../data/schema/source-mappings-v1.json)
- [Dataset guide](../testing/dataset-guide.md)
