# Documentation during development

1. Identify affected requirements, documents, contracts, and architectural decisions.
2. Update documents alongside code. Independent drafting may run in parallel once interfaces are agreed.
3. Add relevant tests and record actual verification results.
4. The implementation owner verifies final prose, diagrams, defaults, and examples against code.
5. Update progress and contribution evidence with work-product references.

Documentation belongs in the same change/review unit, not postponed until submission. Never present planned or untested behaviour as complete.

Run `python scripts/check_docs.py` for internal Markdown links and duplicate ADR numbers. It does not verify remote links or prose accuracy. Review API examples against generated OpenAPI. Code/configuration owns parameters; docs explain and reference them. Use synthetic/redacted examples and follow the [ADR policy](../adr/README.md).

