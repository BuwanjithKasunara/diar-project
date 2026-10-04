# 0001: Local prototype architecture

Date: 2026-09-27  
Status: Accepted

## Context

The repository already uses FastAPI, SQLite, and a browser interface. The earlier README incorrectly described the frontend as React.

## Decision

Retain Python/FastAPI, SQLite, and vanilla JavaScript for a local single-user prototype. Record this inherited choice on this date; the original decision date is unknown.

## Alternatives

React migration; shared hosted service.

## Consequences

Small setup and no frontend build requirement; no account isolation or shared-hosting guarantees.

## Related documents

- [Requirements](../project/scope-and-requirements.md)
- [Architecture](../architecture/overview.md)
- [Verification](../testing/results/development-verification.md)
