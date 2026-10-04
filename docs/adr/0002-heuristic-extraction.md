# 0002: Heuristic extraction with explicit evidence

Date: 2026-09-27  
Status: Accepted

## Context

The proposal discussed neural text classification, but the implemented extractor is dictionary/regex based and has context errors.

## Decision

Improve deterministic extraction with assertion/source evidence and restricted matching. Defer neural training until labelled data and evaluation support it.

## Alternatives

Train/fine-tune a neural classifier; use an external language model.

## Consequences

Explainable and inexpensive, but complex language can still be misclassified. Final documentation must accurately explain this proposal deviation.

## Related documents

- [Requirements](../project/scope-and-requirements.md)
- [Architecture](../architecture/overview.md)
- [Verification](../testing/results/development-verification.md)
