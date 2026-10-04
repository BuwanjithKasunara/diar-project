# Workflows

```mermaid
sequenceDiagram
 actor User
 participant UI as Browser
 participant API as FastAPI
 participant E as Extractors
 participant AI as Alignment and planner
 User->>UI: Inputs, career, visibility
 UI->>API: POST /api/analyze
 API->>E: Validate/extract supplied sources
 E-->>API: Evidence, statuses, warnings
 API->>AI: Consolidated profile
 AI-->>API: Assessment and plan
 API-->>UI: Unsaved report
 UI-->>User: Results and limitations
```

A source failure may still permit analysis if another source is usable. No usable evidence produces a clear error. A later failed request preserves the previous successful interface result.

```mermaid
flowchart LR
 A[Unsaved report] -->|Save| B[POST /api/reports]
 B --> C[Saved ID and history]
 C -->|Open| D[GET /api/reports/id]
 C -->|Delete| E[DELETE /api/reports/id]
```

