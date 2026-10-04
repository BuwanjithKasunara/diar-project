# Development handover

The current report contract is schema version 3. It reports benchmark capability evidence, source scope, and factual GitHub portfolio recency instead of public skill/source/activity grades. GitHub extraction uses a bounded sample of owned public non-fork repository metadata and selected READMEs, retaining evidence provenance and partial-fetch reasons. Read [ADR 0007](../adr/0007-capability-evidence-scoring.md), the [API contract](../api/README.md), and [verification results](../testing/results/development-verification.md) together.

Recommendations must preserve the central distinction: `not_observed` requests documentation, `not_assessed` requests source recovery, and only `explicit_gap` or verified short experience permits development advice. The planner may not turn absence-only observations into learning prerequisites. Fuzzy memberships remain method detail, not a competence label.

`POST /api/analyze` emits v3; explicit saving accepts v2 or v3 during transition. Stored v2 and unversioned JSON is not rewritten or rescored and uses the historical interface branch. The development defaults remain local single-user operation, synthetic fixtures, heuristic extraction, no neural-model training, no framework migration, and no automatic report saving.

Use the verification-results page for actual command outcomes; this handover does not imply a check passed. Live GitHub testing remains optional because deterministic snapshots cover the contract without consuming rate limits. Final submission still needs broader independent evaluation, error analysis, team-confirmed contribution evidence, and report/presentation/video. Synthetic regression fixtures cannot establish general accuracy or benchmark validity.

