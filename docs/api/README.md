# API usage

[FastAPI docs](http://127.0.0.1:8000/docs) and [OpenAPI](http://127.0.0.1:8000/openapi.json) define current contracts.

- `GET /api/health`: liveness.
- `GET /api/benchmarks`: supported careers.
- `GET /api/visibility-levels`: visibility choices.
- `GET /api/config`: current public upload/text limits and activity-window days; no token is exposed.
- `POST /api/analyze`: multipart analysis without saving.
- `POST /api/reports`: explicitly save report JSON.
- `GET /api/reports`: recent saved summaries.
- `GET /api/reports/{id}`: retrieve current or legacy report.
- `DELETE /api/reports/{id}`: delete; success is 204.

```shell
curl -X POST http://127.0.0.1:8000/api/analyze -F "benchmark_identity=Software Engineer" -F "visibility_level=Privacy Focused" -F "linkedin_text=Skills: Python, SQL. Built a REST API using FastAPI."
```

Optional sources are `resume` PDF, `github_username`, and `linkedin_text`. `linkedin_visibility` accepts `unverified` (default), `public`, or `private`; it describes the supplied source, separately from the requested visibility preference. At least one usable source is required. The response includes warnings, present assessment, and separate suggested actions. Submit the unsaved analysis JSON to the save endpoint only after an explicit user choice. Saving returns 201 with `id` and `created_at`; saved-response metadata is not part of a new save request.

Validation errors return explanatory details. Partial sources can coexist with successful analysis. Null means unassessed. Legacy reports may lack evidence/plans. Endpoints have no account ownership enforcement; keep them local.

Errors use `detail: {code, message}`. Unsupported selections, malformed usernames, missing input, and no usable source return 400; upload/text size failures return 413; invalid request fields/schema return 422; absent reports return 404. Reports are ordered newest first and history returns at most 50 summaries.

PDF processing failures (including too many pages) mark that source failed; another usable source can still yield 200. Byte-limit failures reject the request before extraction. The backend processes blocking extraction in a thread pool.
