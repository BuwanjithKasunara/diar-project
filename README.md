# DIAR — Digital Identity Analysis and Recommendation System

DIAR combines résumé PDFs, public GitHub information, and pasted LinkedIn text into an evidence-based profile, compares it with five career benchmarks, and explains suggested improvements.

Results describe evidence detected in the supplied sources—not a person's overall expertise. GitHub output is limited to owned public repositories and reports factual portfolio recency rather than an `active`/`inactive` judgment.

This local single-user academic prototype uses heuristic extraction, knowledge and rules, fuzzy classification, and bounded uniform-cost planning. The frontend is vanilla JavaScript.

## Quick start

From this directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
.\.venv\Scripts\python.exe -m http.server 5173 --bind 127.0.0.1 --directory frontend
```

Open [DIAR](http://127.0.0.1:5173) and [API docs](http://127.0.0.1:8000/docs). Serve the frontend over HTTP rather than opening its HTML file directly.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe scripts/check_docs.py
```

See the [documentation index](docs/README.md), [setup guide](docs/development/setup.md), and [handover](docs/project/handover.md). Analysis does not automatically save reports.
