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
- **Training & Evaluation Script (`backend/train_ml_model.py`)**: Can be run directly to evaluate 5-fold cross-validation performance (97%+ accuracy) and export the trained model artifact (`backend/app/data/career_classifier.joblib`).
- **Prediction Output**: Provides a role prediction, confidence percentage, probability distribution across all roles, and textual feature tokens driving the prediction.

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
- **Frontend**: React, loaded via CDN with an in-browser Babel transform (single `index.html`, no
  npm/build step) so the prototype can be opened directly in a browser. Swap in a Vite/CRA build if you
  want a compiled bundle for deployment.

## Setup & Running

### Backend (.venv Environment Setup)

We recommend using a Python virtual environment (`.venv`) to isolate dependencies:

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
   pip install -r requirements.txt
   ```

3. **Run tests and launch the backend:**
   ```bash
   python -m pytest tests -v                    # Run the full automated regression suite
   python train_ml_model.py                     # Optional: re-train/evaluate ML classifier
   python -m uvicorn app.main:app --reload --port 8000
   ```
   > **Note on `.venv`:** The `.venv` directory contains machine-specific installed packages and is intentionally excluded from Git via `.gitignore`. Anyone cloning this repository can recreate it anytime by following the steps above.

API docs (auto-generated by FastAPI): http://localhost:8000/docs


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
source-specific recommendations and independent report controls are planned follow-ups.

## Extending

- Add a benchmark identity: edit `backend/app/data/benchmarks.json`.
- Add a skill to the taxonomy: edit `backend/app/data/skills_dictionary.json`, under the relevant
  category, as `"canonical name": ["alias1", "alias2", ...]`. Include the canonical name itself as
  the first entry in its own alias list.
- Add a rule: add a block to `backend/app/modules/alignment_engine.py`'s `run_alignment()` and give it
  a unique rule id / priority / reason — it flows automatically through the recommendation engine and
  into the explanation summary.
