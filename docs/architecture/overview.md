# Architecture

A vanilla JavaScript frontend calls a local FastAPI backend. SQLite holds explicitly saved reports.

```mermaid
flowchart LR
 UI[Browser inputs] --> API[Validation]
 API --> E[PDF / text / GitHub extraction]
 E --> P[Identity and evidence]
 P --> A[Benchmarks / rules / fuzzy classification]
 A --> R[Priority ranking]
 A --> S[Uniform-cost planner]
 R --> O[Report and explanations]
 S --> O
 O --> UI
 UI -->|Explicit save / open / delete| DB[(SQLite)]
```

Ranking orders independent suggestions; search chooses combinations under assumed costs. Neither verifies competence. See [data model](data-model.md), [workflows](workflows.md), and [ADRs](../adr/README.md).
