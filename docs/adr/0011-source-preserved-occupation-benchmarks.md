# 0011: Source-preserved occupation benchmarks

Date: 2026-10-04  
Status: Accepted

## Context

The central evidence profile needs a separate, reusable baseline representation. ESCO expresses essential and optional occupation-to-skill relations. O*NET supplies occupation ratings with importance and level scales plus software categories and examples. Combining these as if they used one scale would discard provenance and create unjustified weights.

## Decision

Create occupation benchmark schema `1.0.0` and retain one benchmark per source occupation. ESCO relations remain `essential` or `optional`. O*NET skill and knowledge relations retain their raw importance and level values as `rated`; software categories remain `software` relations with their examples and source flags.

Do not normalize or equate ESCO relationships with O*NET scales. Preserve source concept and occupation identifiers. Mark O*NET requirements with recommended suppression and remove their numeric values from downstream availability when suppression is recommended. Do not treat a software example, hot-technology flag, or in-demand flag as evidence that a candidate has a capability.

## Alternatives

- Merge ESCO and O*NET occupations by title: equal titles do not guarantee equal scope.
- Convert every relationship to a common weight now: there is no validated calibration between the source systems.
- Drop suppressed O*NET relationships: retaining them with an explicit flag preserves provenance and enables auditing.
- Embed candidate evidence inside each benchmark: this would reintroduce per-source comparison and duplicate candidate data.

## Consequences

DIAR can select a benchmark independently and compare one central profile with it. Cross-taxonomy occupation alignment and weighting remain explicit later decisions. Raw O*NET scales must not be presented as calibrated probabilities or knowledge levels.

## Related documents

- [Occupation benchmark schema](../../data/schema/occupation-benchmark-v1.schema.json)
- [Concept catalogue schema](../../data/schema/concept-catalog-v1.schema.json)
- [Central profile decision](0009-central-evidence-profile.md)
