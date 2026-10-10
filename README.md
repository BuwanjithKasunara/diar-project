# DIAR — AI-Based Digital Identity Analysis and Recommendation System

A working prototype of the system described in the project proposal: it consolidates a resume, GitHub
profile, and pasted LinkedIn text into a single Digital Identity Profile, compares it against a chosen
benchmark professional identity, and produces an explainable, prioritised set of recommendations —
taking the user's preferred visibility level (Fully Public / Semi-Public / Privacy Focused) into account.

## Architecture

This mirrors the workflow diagram (`DigitalID_AI_GRP_PRJ_Worlflow.drawio`) and the proposal's Section 10 module list:

| Module | Proposal AI Technique | File |
|---|---|---|
| Information Extraction | NLP / text classification | `backend/app/modules/extraction.py` |
| Identity Construction | Data consolidation | `backend/app/modules/identity_construction.py` |
| Identity Benchmark | Knowledge Representation | `backend/app/data/benchmarks.json` |
| Machine Learning Role Classification | Supervised NLP Classifier (TF-IDF + Softmax) | `backend/app/modules/ml_classifier.py`, `backend/train_ml_model.py`, `backend/app/data/career_profiles_dataset.csv` |
| Digital Identity Alignment Engine | Rule-Based Reasoning + Fuzzy Logic | `backend/app/modules/alignment_engine.py`, `fuzzy_logic.py` |
| Recommendation Engine | Search Algorithm (priority queue) | `backend/app/modules/recommendation_engine.py` |
| Explainable AI | Rule-traced explanations | `backend/app/modules/explainable_ai.py` |
| Digital Identity Report | API response / DB record | `backend/app/main.py`, `database.py` |

**Machine Learning Component & Dataset:**
- **Dataset (`backend/app/data/career_profiles_dataset.csv`)**: Contains labeled profile and resume descriptions spanning all 5 benchmark professional identities (*AI Engineer*, *Data Scientist*, *Software Engineer*, *Researcher*, *Entrepreneur*).
- **ML Pipeline**: Employs an n-gram TF-IDF vectorizer paired with a multinomial logistic regression classifier trained with `scikit-learn`.
- **Training & Evaluation Script (`backend/train_ml_model.py`)**: Can be run directly to evaluate 5-fold cross-validation and a seeded holdout split, saving a [dated evaluation record](docs/testing/model-evaluation.json). `--save-model` explicitly replaces the local trained artifact. Results on this repository dataset do not establish real-profile accuracy.
- **Prediction Output**: Provides a role prediction, model probabilities and matching vocabulary ranked by TF-IDF weight. Vocabulary matches are not measured class contributions, and probabilities are not calibrated confidence. Empty/unmatched vocabulary receives an insufficient-evidence result; model failures preserve rule analysis. No evaluated abstention threshold is used.

**Note on scope / simplifications made to get a runnable prototype:**
- **NLP module**: implemented as a fast, fully explainable dictionary-driven text classifier
  (`skills_dictionary.json` + regex heuristics) rather than a trained spaCy/Transformers model. This
  keeps the system deployable offline with no model downloads, while remaining a direct stand-in for
  the neural classifier described in the proposal — the module boundary (`extraction.py`) is where a
  real NER/transformer model would be swapped in.
  - **Alias / synonym matching**: `skills_dictionary.json` maps each canonical skill to a list of
    known synonyms and abbreviations (e.g. `machine learning` ← `ml`; `kubernetes` ← `k8s`;
    `javascript` ← `js`), so phrasing differences don't cause a miss.
  - **Typo tolerance**: remaining unmatched single words are compared against known skill names using
    Python's built-in `difflib` similarity ratio (cutoff 0.82), catching small misspellings (e.g.
    "Pythom" → `python`, "Dockr" → `docker`) without needing a trained ML model or any extra
    dependency. Multi-word phrases are excluded from fuzzy matching to avoid false positives.
- **Fuzzy Logic**: implemented as a small dependency-free triangular-membership module
  (`fuzzy_logic.py`), equivalent in spirit to `scikit-fuzzy`'s `trimf`, so the backend has no heavy
  numerical stack to install. `scikit-fuzzy` is listed as the proposed library in the write-up; swapping
  it in is a drop-in change if you want the exact library named in Section 9.
- **GitHub**: uses the real public GitHub REST API (`api.github.com`) — no simulation.
  - Profile and repository requests are handled separately. If the profile loads but the
    repository request fails, usable profile evidence is retained and a notice is shown.
  - The prototype analyses one page of up to 100 public repositories sorted by update time,
    including forks in that page limit; portfolio metrics use only non-fork repositories.
    Pagination links and the profile's public repository count identify incomplete coverage.
  - Repository count, activity, and language-diversity recommendations are withheld when
    repository retrieval fails or coverage is incomplete. A successfully retrieved empty
    portfolio remains distinguishable from unavailable data.
- **LinkedIn**: LinkedIn has no public scraping API, so the prototype accepts pasted profile text
  (headline / about / skills / experience) which is run through the same NLP extraction pipeline used
  for the resume.
- **Privacy review**: The visibility preference guides source-specific advice to reduce unnecessary
  online exposure. DIAR checks returned public GitHub profile/repository metadata and supplied
  LinkedIn text. LinkedIn audience/settings are not verified. Resume contact information is treated as
  job-application information unless the user marks that copy publicly available. Results show masked
  evidence and scan coverage; a metadata scan is not a complete account or repository-file audit.
- **Frontend**: Plain JavaScript (`index.html` and `report-review.js`), with no npm/build step.

## Setup & Running

### Optional public repository file privacy review

Check **Also review public README and supported root text files** to include bounded
file review with a GitHub username. It is off by default. DIAR checks one root README
format plus `CONTRIBUTING.md` and `SECURITY.md` in up to five fetched public repositories,
including forks. It does not scan nested/source files, private repositories or history.
There are at most 25 extra requests, 100 KiB per file, 1 MiB decoded text in total
and a 20-second scan budget within the backend analysis deadline. Coverage can be partial.

Findings show masked excerpts, repository/path, line and revision plus review advice.
Example/contributor contacts may be flagged; ownership and necessity of disclosure are
not verified. Editing the latest file does not remove historical copies. Raw downloaded
files are never saved, even with Retain extracted text; career scores/ML inputs remain
independent. No files or profile settings are changed automatically.
See the [decision record](docs/privacy/repository-file-scanning.md) for limits and
the [delivery record](docs/improvements/id-9-delivery.md) for verification.

### Analysis recovery

While another analysis runs, the previous successful report stays visible.
Failed attempts retain it; Cancel analysis stops the browser from waiting.
The browser has a 45-second timeout, and backend report construction has a
40-second deadline after upload validation. Backend deadline errors do not save
a report, but browser cancellation/network failure may occur while the server
continues and saves one. Check `/api/reports` before retrying if needed; automatic
retries are not performed. Use the Saved reports panel to check history.
If ML prediction fails, DIAR still returns its available rule-based analysis.
See the [recovery delivery record](docs/improvements/id-7-delivery.md) for limits.

### Input and evidence limits

Supply at least one resume PDF, GitHub username or nonempty LinkedIn text.
Use a username rather than a GitHub URL. Resume PDFs must have readable text,
contain at most 30 pages and be no larger than 5 MiB; password-protected/scanned
PDFs are not supported. Extracted PDF text and LinkedIn input each have a
100,000-character limit. Invalid uploads must be corrected or removed before retrying.
If GitHub fails and no other input is available, DIAR does not save an empty report.

Skill gaps describe information not detected in supplied evidence. Without supported
skill mentions, alignment judgements and skill-gap advice are withheld. Privacy
findings can still appear for short contact-containing text. Unknown experience is
not treated as zero years in recommendations; estimates use explicit totals or
year ranges in labelled experience sections and exclude education dates.
Source coverage describes the supplied inputs, not verified account completeness.
See the [improvement plan](docs/improvements/implementation-plan.md) and delivery
records in [the documentation index](docs/README.md) for scope and verification.

### Backend (.venv Environment Setup)

Verified environment: **Python 3.12.10**, Windows. CI uses the same Python version on Ubuntu (remote run pending until push). Use `requirements-lock.txt` for the full runtime/development stack; `requirements.txt` pins direct runtime dependencies and `requirements-dev.txt` adds test dependencies. The lock was resolved in a fresh environment, including transitive versions.

Use a Python virtual environment (`.venv`) to isolate dependencies:

1. **Create and activate the virtual environment:**
   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

2. **Install dependencies:**
   ```bash
   cd backend
   python -m pip install -r requirements-lock.txt
   ```

3. **Run tests and launch the backend:**
   ```bash
   python -m pytest tests -v                    # Run the full automated regression suite
   python train_ml_model.py                     # Evaluate and record metrics
   python train_ml_model.py --save-model        # Optional: also replace local model
   python -m uvicorn app.main:app --reload --port 8000
   ```
   > **Note on `.venv`:** The `.venv` directory contains machine-specific installed packages and is intentionally excluded from Git via `.gitignore`. Anyone cloning this repository can recreate it anytime by following the steps above.

API docs (auto-generated by FastAPI): http://localhost:8000/docs

### Online presence and saved reports

Fully Public supports an intentional professional presence; Semi-Public supports selected
public work; Privacy Focused offers private portfolio development and selective sharing.
The exposure review supports email/phone patterns, explicitly labelled street addresses and
dates of birth. It checks public GitHub metadata and supplied LinkedIn text, with masked
evidence and coverage limits. Optional bounded root-file review is available; account settings remain unverified.

Saved report protection is selected independently:

| `report_redaction` | Effect on DIAR's saved/returned report |
|---|---|
| `mask_contacts` (default) | Mask common email and phone patterns throughout report text |
| `mask_contacts_and_handle` | Also hide GitHub username fields and known handle/URL references |
| `none` | Retain extracted text; exposure evidence remains masked |

Masking is pattern-based; names and identifying prose can remain. Career scores and ML inputs
are computed before report protection. New reports store their policy in `report_metadata`.
Legacy reports without metadata use their former visibility-to-protection mapping on read,
without rewriting the original stored row or regenerating its findings.

`POST /api/analyze` accepts optional `resume_publicly_shared` (boolean, default false) and
`report_redaction` (one of the values above; invalid values return 400). A private application
resume does not trigger public-exposure advice. A declared public copy is reviewed on that
declaration; DIAR does not verify where it was posted.

`GET /api/reports` and `GET /api/reports/{id}` follow the saved protection policy.
`DELETE /api/reports/{id}` removes that saved row (204); an unknown/deleted ID returns 404.
The result page asks for confirmation and keeps the report visible if deletion fails. Deletion
does not change external profiles, remove backups, or promise forensic erasure of SQLite data.
This local prototype has no authentication or per-user report access controls. Run it locally;
report masking is not an access-control system.


### Advanced Capabilities Implemented
1. **Context-Aware Skill Categorization**: Classifies skill mentions into `claimed`, `planned` (trajectory intent), `negated` (explicit lack of experience), and `uncertain` (beginner).
2. **Frequency Normalization & Noise Suppression**: Sublinear term frequency saturation capping prevents keyword stuffing.
3. **Explicit Data Source State Tracking**: Ingestion states (`not_supplied`, `partial`, `failed`, `analysed`) prevent false penalties by flagging *insufficient evidence*.
4. **Multi-Factor Contextual Scoring**: Blends active skill claims, learning trajectories, and source authority multipliers.
5. **Repository Recency & Relevance**: Dynamic commit recency analysis flags stale codebases (>2y) and evaluates domain relevance.
6. **Privacy Review & Visibility Recommendations**: Connects masked, source-specific exposure candidates and coverage to actionable recommendations; portfolio suggestions respect Fully Public, Semi-Public, and Privacy Focused goals.
7. **Automated Test Suite**: Full `pytest` regression suite in `backend/tests/test_pipeline.py`.


### Frontend
Just open `frontend/index.html` in a browser (it talks to `http://localhost:8000` by default).
To point it at a different backend URL, set `window.DIAR_API_BASE` before the app script runs, e.g.
add `<script>window.DIAR_API_BASE = "http://localhost:8000";</script>` in `index.html`, or serve it with
a tiny static server:
```bash
cd frontend
python3 -m http.server 5173
```
then visit http://localhost:5173

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Liveness check |
| `/api/benchmarks` | GET | List benchmark identities (AI Engineer, Software Engineer, Data Scientist, Researcher, Entrepreneur) |
| `/api/visibility-levels` | GET | List visibility levels |
| `/api/analyze` | POST | Multipart form: `resume` (PDF, optional), `github_username` (optional), `linkedin_text` (optional), `benchmark_identity`, `visibility_level` → full Digital Identity Report |
| `/api/reports` | GET | Report history (stored in SQLite) |
| `/api/reports/{id}` | GET | Retrieve a past report |

## Development documentation

See [project documentation](docs/README.md), including the privacy requirement
realignment record and staged implementation plan. The evidence foundation is Part 1;
source-specific recommendations and independent report controls are implemented.

## Extending

- Add a benchmark identity: edit `backend/app/data/benchmarks.json`.
- Add a skill to the taxonomy: edit `backend/app/data/skills_dictionary.json`, under the relevant
  category, as `"canonical name": ["alias1", "alias2", ...]`. Include the canonical name itself as
  the first entry in its own alias list.
- Add a rule: add a block to `backend/app/modules/alignment_engine.py`'s `run_alignment()` and give it
  a unique rule id / priority / reason — it flows automatically through the recommendation engine and
  into the explanation summary.

## Review and export saved reports

The Saved reports panel lists the latest 50 reports in this local prototype.
Refresh the list and open a report after refreshing the page. Opening uses the
saved protected response, does not reanalyse it, and does not replace form inputs.
Loading and failed requests keep the previous report available; report actions
are disabled while another report is opening or analysis/deletion is running.

Export JSON downloads the displayed report under its stored protection policy.
The filename contains only its report ID. Print report / Save PDF uses your
browser's print dialog and includes the full recommendation list even when the
screen is filtered. Exports include benchmark, creation time, protection metadata,
coverage and recorded scan limitations. Retained-text exports may contain personal
information. Deleting a saved row does not erase downloads, backups or source data.

Filter recommendations by career, privacy or legacy/uncategorized actions and
priority. Original ranks remain unchanged. Suggested first steps use the existing
first three ranked actions. Repository-file actions have a separate shortcut list;
privacy-card links reveal actions hidden by filters. Recommendation evidence links
jump to the recorded evidence. Historical actions without categories stay visible
under All and Legacy / uncategorized; they are not silently reclassified.

History has no authentication or report ownership and is intended for local use.
Shared hosting requires separately planned access control. Print styling is
provided; native print dialog/PDF output has not yet been visually verified.

## Reproducible verification

From `backend`, run `python -m pip check` then `python -m pytest tests -q`.
The suite blocks real requests HTTP calls, uses temporary SQLite databases, and
trains its model from the repository CSV into temporary storage. No credentials,
profile requests or external model downloads are required after package install.
GitHub Actions repeats installation, dependency checks, regression tests and
`python train_ml_model.py --output evaluation-ci.json` on main pushes and PRs.

See [model evaluation and dataset limits](docs/testing/model-evaluation.md).
The dataset's original source, consent and license are unknown. Evaluation removes
normalized exact duplicates before splitting, records class counts and split indices,
and screens holdout near duplicates; shared templates and semantic leakage remain
possible. Probabilities are not calibrated confidence. A missing model is trained
locally from the CSV on first use; failed load/training leaves rule analysis available.
The evaluation command writes metrics only unless `--save-model` is supplied.
