# 0005: Explicit report persistence

Date: 2026-09-27  
Status: Accepted

## Context

Automatic persistence retains potentially sensitive evidence without a separate user action. Existing reports must remain readable.

## Decision

Analyse without saving; add explicit save/delete and retain legacy JSON. Keep loopback operation and no account system for this phase.

## Alternatives

Continue automatic saving; introduce accounts and migrations now.

## Consequences

Users control retention. Local endpoints still need trusted single-user access; deletion is not forensic erasure.

## Related documents

- [Requirements](../project/scope-and-requirements.md)
- [Architecture](../architecture/overview.md)
- [Verification](../testing/results/development-verification.md)
