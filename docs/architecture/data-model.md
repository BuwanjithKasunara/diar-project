# Data model

New reports carry schema, benchmark, and planner versions, selected role/visibility, profile, comparison, gap analysis, recommendations, explanations, and a suggested plan.

Sources use `not_supplied`, `analysed`, `partial`, or `failed`, with reasons. Skill evidence retains canonical skill, source, excerpt, method, and assertion. Only positive claims contribute to matching. Null assessments mean unavailable evidence; source coverage is separate from competence.

Plans report status, steps, effort, addressed/unresolved objectives, expanded states, and optimality within their bounded model. Hypothetical actions do not change current scores.

SQLite rows store benchmark, visibility, optional GitHub username, timestamp, and JSON. IDs are assigned on saving. Legacy JSON remains unchanged; readers tolerate missing version/evidence/planning fields without inventing them.

See [API usage](../api/README.md). Generated OpenAPI defines exact current wire fields.
