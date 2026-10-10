# Project documentation

- [Incremental improvements plan](improvements/implementation-plan.md): nine scoped
  improvements, execution order, branch/author assignments, acceptance checks and
  required implementation records. Public repository file scanning precedes the
  report-history and recommendation UI improvements.
- Group 1 delivery records: [input validation](improvements/id-1-delivery.md),
  [career evidence](improvements/id-2-delivery.md) and
  [skill context](improvements/id-3-delivery.md).
- [Analysis recovery and responsiveness](improvements/id-7-delivery.md): prior-report
  preservation, cancellation/deadline behavior, worker isolation and ML failure fallback.
- [Repository file privacy decision](privacy/repository-file-scanning.md) and
  [ID 9 delivery](improvements/id-9-delivery.md): bounded optional root-file review,
  masked file/line evidence, coverage, transport limits and verification.
- [Privacy requirement realignment](privacy/realignment.md): requirement misunderstanding,
  intended behavior, evidence limits, implementation stages, verification and rollback.
- [Privacy implementation plan](privacy/implementation-plan.md): detailed specification
  and the three separate branch/PR boundaries used to correct the feature.

Update the realignment record when each part is implemented and merged. Planned behavior
must remain labelled as planned until its implementation is verified.

- [ML prediction evidence](improvements/id-4-delivery.md).
- [Saved report history/export](improvements/id-5-delivery.md) and
  [recommendation navigation](improvements/id-6-delivery.md).
- [Reproducible setup delivery](improvements/id-8-delivery.md) and
  [dataset/evaluation record](testing/model-evaluation.md).
