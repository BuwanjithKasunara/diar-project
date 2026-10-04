# Local setup

Use Python 3.11 or later. Follow the [root quick start](../../README.md). Windows uses `.venv\Scripts\python.exe`; macOS/Linux uses `.venv/bin/python`. Development installation uses `backend/requirements-dev.txt`; runtime-only installation uses `backend/requirements.txt`.

Serve frontend HTTP on loopback port 5173 and backend on loopback port 8000. File URLs are unsupported. Public GitHub analysis needs network access; PDF/text-only analysis does not.

## Configuration

[Backend configuration](../../backend/app/config.py) owns environment variable names/defaults:

- `DIAR_MAX_PDF_BYTES`: 5242880 (5 MB).
- `DIAR_MAX_PDF_PAGES`: 30.
- `DIAR_MAX_TEXT_CHARS`: 50000.
- `DIAR_ACTIVITY_DAYS`: 180.
- `DIAR_MAX_REPOS`: 500.
- `DIAR_MAX_ACTIONS`: 20.
- `DIAR_MAX_STATES`: 50000.
- `DIAR_GITHUB_TOKEN`: optional backend token.
- `DIAR_DB_PATH`: optional SQLite file path; default is `backend/app/diar.db`. Its parent directory must exist.

Overrides are read at backend startup; positive numeric values are required. Restart after changing them.

The frontend obtains public size/page/text limits from `GET /api/config`; it validates byte/text limits before submission and explains that PDF page validation occurs on the backend. Use unlocked text PDFs, not scanned images. Current allowed frontend origins are `http://127.0.0.1:5173` and `http://localhost:5173`.

An optional server-side GitHub token supports authenticated API limits. Never commit it or expose it to frontend code.

The supplied `.venv` may refer to a Python installation absent on another computer. If its interpreter fails, create a fresh environment under a new name and substitute its interpreter in the commands. Development verification used `.venv-dev`; no existing environment needs to be deleted.

CORS is not authentication. This release is for local single-user operation, not shared hosting.

## Checks

From project root run `python -m pytest backend/tests -q` and `python scripts/check_docs.py` using the virtual environment interpreter. Tests must use temporary databases, never saved user reports. Installing dependencies requires package-network access.
