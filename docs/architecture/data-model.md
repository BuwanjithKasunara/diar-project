# Data model

New analyses carry `schema_version: 3`, `benchmark_version: 3`, the planner version, selected role/visibility, source/profile data, evidence, `assessment`, recommendations, explanations, and a suggested plan.

`assessment` has three typed components:

- `benchmark_evidence`: score, capability counts/results, fuzzy memberships, method, and limitation text.
- `source_scope`: usable, partial, failed, and unsupplied source lists/counts.
- `github_portfolio_recency`: availability, observation window, owned public non-fork repository count, recently pushed count, and latest repository push timestamp.

Capability results retain their weight, strongest strength, state, matching concepts, and references to supporting evidence. States are `evidenced`, `weakly_evidenced`, `not_observed`, `not_assessed`, or `explicit_gap`.

Sources use `not_supplied`, `analysed`, `partial`, or `failed`, with reasons. Evidence retains a stable identifier, canonical concept, source, origin/artifact type, repository locator when applicable, excerpt, method, assertion, and strength. Positive evidence supports capability matching; explicit negative self-statements can establish `explicit_gap`. Missing evidence alone does not.

Plans report status, steps, effort, addressed/unresolved objectives, expanded states, and optimality within their bounded model. Documentation actions address unobserved evidence; development actions require an explicit gap or verified short experience. Hypothetical actions do not change current scores.

SQLite rows store benchmark, visibility, optional GitHub username, timestamp, and report JSON. IDs are assigned only on saving. The save endpoint temporarily accepts version 2 and version 3, and report history derives a nullable schema version from the stored JSON without changing the database schema. Existing version 2 and unversioned JSON is not migrated, normalised, or rescored; readers tolerate absent v3 fields, and the interface uses a historical rendering branch.

See [API usage](../api/README.md). Generated OpenAPI defines exact current wire fields.

