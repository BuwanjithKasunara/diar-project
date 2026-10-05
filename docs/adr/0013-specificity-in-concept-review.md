# 0013: Preserve specificity in concept review

Date: 2026-10-05  
Status: Accepted

## Context

In the synthetic pilot, two Sol reviewers disagreed on 38 of 125 concept mappings. Many disputes involved a named software product and a broad ESCO/O*NET software category. A blind Astra Low review supplied a third AI judgment, but the three models cannot establish human ground truth. The version 1 annotation schema has no field for a narrower-than or example-of relationship.

## Decision

For canonical concept annotation, require the catalogue concept to preserve the claim's intended specificity. A product that is merely an example of a broader category is not an equivalent concept. When no sufficiently specific concept exists, record `none` and describe the broader category in the rationale. Reserve `needs_context` for ambiguous claim meaning and `multiple_valid` for independently supported concepts. Keep AI pilot outcomes separate from future human reviewed labels.

This is an annotation rule, not a claim that broader relationships are useless. A future versioned relationship field may record them without treating them as canonical equivalence.

## Alternatives

- Accept every source example as an exact category match: this loses the difference between a named tool and a broad capability.
- Reject all broad-category relationships permanently: this discards useful benchmark context that a later typed relation could preserve.

## Consequences

Some named products remain unmapped under the current schema even when a broader benchmark category is related. This conservative choice prevents a category link from silently becoming an exact match. Human reviewers must apply the clarified rubric to disputed cases; the existing AI pilot answers were made under the earlier wording and are not retroactively relabelled. No XGBoost target is created by this decision.

## Related documents

- [Annotation rubric](../testing/annotation-rubric.md)
- [Independent annotation decision](0012-independent-evidence-level-annotation.md)
