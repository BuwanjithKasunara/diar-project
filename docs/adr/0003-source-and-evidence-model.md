# 0003: Source and evidence model

Date: 2026-09-27  
Status: Accepted

## Context

Missing or failed sources previously resembled zero ability. Skill strings alone did not retain their justification.

## Decision

Track independent source statuses and skill assertions. Use unknown/null assessments when evidence is insufficient; count supported positive claims only.

## Alternatives

Treat absent sources as zero; silently ignore failed sources.

## Consequences

Reports grow and legacy fields can be absent. Readers must handle older reports without inventing facts.

## Related documents

- [Requirements](../project/scope-and-requirements.md)
- [Architecture](../architecture/overview.md)
- [Verification](../testing/results/development-verification.md)
