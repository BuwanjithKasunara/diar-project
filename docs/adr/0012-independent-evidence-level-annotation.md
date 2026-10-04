# 0012: Independent evidence-level annotation

Date: 2026-10-04  
Status: Accepted

## Context

The filtered synthetic profiles retain generation metadata for sampling and audit. No field in that metadata is an independently assessed knowledge level. Exact ESCO/O*NET matches also require semantic review because the same label can refer to multiple source concepts. Model experiments need an explicit annotation target and a way to distinguish reviewed answers from generated labels.

## Decision

Use local review packets for concept mapping and for evidence-supported levels of individual skills. Hide generation metadata from reviewers and keep it in separate internal manifests. The level rubric has `insufficient_evidence`, `foundational`, `applied`, and `advanced`. Insufficient evidence is an abstention state, not a low proficiency score. Positive levels require cited professional evidence beyond a skill-list claim.

Two distinct human reviewers label each task independently. Matching decisions become resolved records; disagreements require a third reviewer. Task digests prevent reuse of annotations against changed evidence. Review files, internal manifests, and generated packets stay local and untracked. No synthetic seniority, cohort, job family, seed role, sample group, or O*NET occupation level is used as a knowledge-level target.

## Alternatives

- Reuse synthetic seniority or cohort as a target: these are generation instructions and can leak from text and IDs.
- Treat a listed skill as demonstrated proficiency: the list provides a claim without proof of use.
- Let one automated pass create gold labels: this would not provide independent evidence.
- Force one concept ID for every ambiguous label: ESCO and O*NET can both contain valid but different concepts.

## Consequences

The pipeline can prepare a reproducible, blinded pilot and validate human responses without claiming that labels already exist. Two reviewers and adjudication add work. The first pilot is synthetic and cannot establish model generalization. XGBoost experimentation remains gated on completed reviewed labels and a profile-level holdout split.

## Related documents

- [Annotation rubric and workflow](../testing/annotation-rubric.md)
- [Annotation schema](../../data/schema/review-annotation-v1.schema.json)
- [Central profile decision](0009-central-evidence-profile.md)
