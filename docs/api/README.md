# API usage

[FastAPI docs](http://127.0.0.1:8000/docs) and [OpenAPI](http://127.0.0.1:8000/openapi.json) define current contracts.

- `GET /api/health`: liveness.
- `GET /api/benchmarks`: supported careers.
- `GET /api/visibility-levels`: visibility choices.
- `GET /api/config`: current public upload/text, GitHub README, repository, and recency-window limits; no token is exposed.
- `POST /api/analyze`: multipart analysis without saving; returns report schema version 3 only.
- `POST /api/reports`: explicitly save version 2 or version 3 report JSON during the compatibility period.
- `GET /api/reports`: recent saved summaries.
- `GET /api/reports/{id}`: retrieve current or legacy report.
- `DELETE /api/reports/{id}`: delete; success is 204.

```shell
curl -X POST http://127.0.0.1:8000/api/analyze -F "benchmark_identity=Software Engineer" -F "visibility_level=Privacy Focused" -F "linkedin_text=Skills: Python, SQL. Built a REST API using FastAPI."
```

Optional sources are `resume` PDF, `github_username`, and `linkedin_text`. `linkedin_visibility` accepts `unverified` (default), `public`, or `private`; it describes the supplied source separately from the requested visibility preference. At least one usable source is required. Submit the unsaved analysis JSON to the save endpoint only after an explicit user choice. Saving returns 201 with `id` and `created_at`; saved-response metadata is not part of a new save request.

## Version 3 assessment

The `assessment` object contains three neutral observations:

- `benchmark_evidence`: numeric evidence score, capability counts/results, fuzzy memberships for method inspection, scoring method, and limitation text. Capability results carry one of `evidenced`, `weakly_evidenced`, `not_observed`, `not_assessed`, or `explicit_gap` and reference their supporting evidence.
- `source_scope`: lists/counts for usable, partial, failed, and unsupplied sources.
- `github_portfolio_recency`: availability, configured window, owned public non-fork repository count, recently pushed count, and latest repository push timestamp. It never returns an `active` or `inactive` judgment.

Evidence records retain stable identifiers and provenance. Version 3 exposes `origin`, the normalized `artifact_type`, `repository_locator` where applicable, `excerpt`, `extraction_method`, `assertion`, and `strength`; the inherited `repository` and `method` fields remain available during compatibility. GitHub limitations and partial-fetch reasons remain visible. These fields describe evidence found in supplied sources; they do not certify competence.

Report-history items include nullable `schema_version`. A null value identifies a stored report that predates explicit versioning. `GET /api/reports/{id}` returns the stored report content without recalculating or rewriting it, adding only persistence metadata. The interface labels version 2 and unversioned results **Historical heuristic—not recalculated**, collapses their old grades, and offers a new analysis rather than silently converting them.

Validation errors return explanatory details. Partial sources can coexist with successful analysis. Null means unassessed. Legacy reports may lack evidence/plans/assessment fields. Endpoints have no account ownership enforcement; keep them local.

Errors use `detail: {code, message}`. Unsupported selections, malformed usernames, missing input, and no usable source return 400; upload/text size failures return 413; invalid request fields/schema return 422; absent reports return 404. Reports are ordered newest first and history returns at most 50 summaries.

PDF processing failures (including too many pages) mark that source failed; another usable source can still yield 200. Byte-limit failures reject the request before extraction. The backend processes blocking extraction in a thread pool.

