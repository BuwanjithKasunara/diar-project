# 0004: Uniform-cost action planning

Date: 2026-09-27  
Status: Accepted

## Context

A priority queue that orders recommendations does not explore alternative plans. DIAR needs a small explainable combination planner.

## Decision

Retain ranking as baseline and use bounded uniform-cost search over positive-cost compatible actions and prerequisites. Return explicit fallback on limits/unreachable goals.

## Alternatives

Greedy search; A* with an unvalidated heuristic; ranking only.

## Consequences

Optimality applies only to completed search within the candidate model. Curated relative costs need validation and do not estimate time.

## Related documents

- [Requirements](../project/scope-and-requirements.md)
- [Architecture](../architecture/overview.md)
- [Verification](../testing/results/development-verification.md)
