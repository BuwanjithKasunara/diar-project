"""
Information Extraction Module (Natural Language Processing)
-------------------------------------------------------------
Extracts structured professional attributes (skills, education,
experience, certifications, projects) from unstructured text sources:
resume PDFs, GitHub profile data, and pasted LinkedIn text.

Technique: alias-aware, typo-tolerant keyword classification against a
curated skills taxonomy, combined with lightweight regex heuristics
for education, experience and certification detection. This acts as
the "Neural Network / Text Classification Model" stage described in
the project proposal: in this prototype it is implemented as a fast,
fully explainable classifier (a dictionary-driven text classifier),
which keeps the pipeline deployable offline (no model downloads, no
heavy ML dependencies) while remaining a direct stand-in for a trained
NER/classification model in a production build.

Two matching passes are used:
  1. Exact / alias matching - each canonical skill (e.g. "machine
     learning") is matched against itself AND a curated list of
     synonyms and abbreviations (e.g. "ml"), so phrasing differences
     don't cause a miss.
  2. Fuzzy single-word matching - remaining unmatched words in the
     text are compared against single-word skill names using
     difflib's sequence-matching ratio, catching minor typos
     (e.g. "Dockr" -> "docker") without a full ML model.
"""
import difflib
import json
import re
import os
from typing import Optional
import fitz  # PyMuPDF
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

with open(os.path.join(DATA_DIR, "skills_dictionary.json")) as f:
    SKILLS_DICT = json.load(f)

# Flatten {category: {canonical: [aliases]}} into two lookup structures:
#   ALIAS_TO_CANONICAL: every alias/canonical phrase -> its canonical skill name
#   CANONICAL_SKILLS:   the full set of canonical skill names
ALIAS_TO_CANONICAL = {}
for _category, _skills in SKILLS_DICT.items():
    for _canonical, _aliases in _skills.items():
        for _alias in _aliases:
            ALIAS_TO_CANONICAL[_alias.strip().lower()] = _canonical

# Sorted longest-first so multi-word aliases are matched before shorter
# substrings that might otherwise shadow them (e.g. "node.js" before "js").
ALL_ALIAS_PATTERNS = sorted(ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)

# Single-word canonical skills / aliases are candidates for typo-tolerant
# fuzzy matching (multi-word phrases are skipped to avoid false positives).
SINGLE_WORD_ALIASES = {a: c for a, c in ALIAS_TO_CANONICAL.items() if " " not in a.strip() and len(a.strip()) > 2}

CERT_KEYWORDS = ["certified", "certificate", "certification", "credential"]
EDU_KEYWORDS = ["bachelor", "master", "phd", "b.sc", "bsc", "msc", "m.sc", "degree",
                "university", "college", "diploma", "undergraduate", "graduate"]
EXPERIENCE_HEADER = re.compile(r"(work experience|professional experience|experience)", re.I)
PROJECT_HEADER = re.compile(r"(projects|portfolio)", re.I)
SKILLS_HEADER = re.compile(r"(technical skills|core competencies|skills)", re.I)

FUZZY_MATCH_CUTOFF = 0.82  # similarity threshold (0-1); higher = stricter, fewer false positives.
# Tuned empirically: catches common single-letter typos (e.g. "Pythom" -> python,
# "Dockr" -> docker) while keeping unrelated English words (e.g. "must", "dust",
# "gust" vs. "rust") below the threshold and therefore unmatched.


def _find_skills(text: str, fuzzy: bool = True) -> list:
    """Returns the set of canonical skill names detected in `text`."""
    text_lower = " " + re.sub(r"\s+", " ", text.lower()) + " "
    found_canonical = set()
    matched_spans = []

    # Pass 1: exact alias / synonym matching (word-boundary aware)
    for alias in ALL_ALIAS_PATTERNS:
        alias_clean = alias.strip()
        if not alias_clean:
            continue
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(alias_clean) + r"(?![a-zA-Z0-9])"
        match = re.search(pattern, text_lower)
        if match:
            found_canonical.add(ALIAS_TO_CANONICAL[alias])
            matched_spans.append((match.start(), match.end()))

    # Pass 2: typo-tolerant fuzzy matching on remaining single words only
    if fuzzy:
        already_covered = set()
        for start, end in matched_spans:
            already_covered.update(range(start, end))

        words = list(re.finditer(r"[a-zA-Z][a-zA-Z0-9+#./-]{2,}", text_lower))
        candidate_pool = list(SINGLE_WORD_ALIASES.keys())
        for m in words:
            w_start, w_end = m.start(), m.end()
            if w_start in already_covered:
                continue  # already matched exactly, skip
            word = m.group().strip(".")
            if word in SINGLE_WORD_ALIASES:
                found_canonical.add(SINGLE_WORD_ALIASES[word])
                continue
            close = difflib.get_close_matches(word, candidate_pool, n=1, cutoff=FUZZY_MATCH_CUTOFF)
            if close:
                found_canonical.add(SINGLE_WORD_ALIASES[close[0]])

    return sorted(found_canonical)


def _find_certifications(text: str) -> list:
    lines = text.split("\n")
    certs = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in CERT_KEYWORDS) and len(line.strip()) > 0:
            certs.append(line.strip())
    return certs[:20]


def _find_education(text: str) -> list:
    lines = text.split("\n")
    edu = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in EDU_KEYWORDS) and len(line.strip()) > 0:
            edu.append(line.strip())
    return edu[:10]


def _extract_section(text: str, header_pattern: re.Pattern, max_chars: int = 1500) -> str:
    match = header_pattern.search(text)
    if not match:
        return ""
    start = match.end()
    return text[start:start + max_chars].strip()


def extract_from_resume_text(raw_text: str) -> dict:
    """Extracts structured attributes from raw resume text."""
    skills = _find_skills(raw_text)
    certifications = _find_certifications(raw_text)
    education = _find_education(raw_text)
    experience_section = _extract_section(raw_text, EXPERIENCE_HEADER)
    projects_section = _extract_section(raw_text, PROJECT_HEADER)

    # crude years-of-experience heuristic: count 4-digit year ranges e.g. 2019-2023
    year_ranges = re.findall(r"(20\d{2}|19\d{2})\s*[-–—to]{1,4}\s*(20\d{2}|present|current)", raw_text, re.I)
    years_experience = 0
    for start, end in year_ranges:
        try:
            start_y = int(start)
            end_y = 2026 if not end.isdigit() else int(end)
            years_experience = max(years_experience, max(0, end_y - start_y))
        except ValueError:
            continue

    return {
        "source": "resume",
        "skills": skills,
        "certifications": certifications,
        "education": education,
        "experience_snippet": experience_section,
        "projects_snippet": projects_section,
        "estimated_years_experience": years_experience,
        "raw_text_length": len(raw_text),
    }


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def extract_from_github(username: str, github_token: Optional[str] = None) -> dict:
    """Pulls public profile + repo data from the GitHub REST API and
    classifies languages / activity / project descriptions."""
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    profile_url = f"https://api.github.com/users/{username}"
    repos_url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"

    try:
        profile_resp = requests.get(profile_url, headers=headers, timeout=10)
        repos_resp = requests.get(repos_url, headers=headers, timeout=10)
    except requests.RequestException as e:
        return {"source": "github", "error": str(e), "skills": [], "languages": [],
                 "repo_count": 0, "profile_complete": False}

    if profile_resp.status_code == 404:
        return {"source": "github", "error": f"GitHub user '{username}' not found",
                 "skills": [], "languages": [], "repo_count": 0, "profile_complete": False}
    if profile_resp.status_code in (403, 429):
        return {"source": "github", "error": "GitHub API rate limit reached while fetching this profile; "
                 "try again shortly or supply a GitHub token.",
                 "skills": [], "languages": [], "repo_count": 0, "profile_complete": False}
    if profile_resp.status_code != 200:
        return {"source": "github", "error": f"GitHub API returned status {profile_resp.status_code} for '{username}'",
                 "skills": [], "languages": [], "repo_count": 0, "profile_complete": False}

    profile = profile_resp.json()
    repos = repos_resp.json() if repos_resp.status_code == 200 else []

    languages = sorted({r.get("language") for r in repos if r.get("language")})
    descriptions_text = " ".join([r.get("description") or "" for r in repos])
    topic_text = " ".join([" ".join(r.get("topics", [])) for r in repos if isinstance(r.get("topics"), list)])
    combined_text = f"{descriptions_text} {topic_text} {profile.get('bio') or ''}"
    skills = _find_skills(combined_text)

    non_fork_repos = [r for r in repos if not r.get("fork")]
    recently_updated = [r for r in non_fork_repos if r.get("updated_at", "") >= "2025-01-01"]

    profile_complete = bool(profile.get("bio")) and bool(profile.get("name")) and len(non_fork_repos) > 0

    return {
        "source": "github",
        "username": username,
        "name": profile.get("name"),
        "bio": profile.get("bio"),
        "public_repos": profile.get("public_repos", 0),
        "followers": profile.get("followers", 0),
        "repo_count": len(non_fork_repos),
        "recently_active_repo_count": len(recently_updated),
        "languages": [l.lower() for l in languages],
        "skills": skills,
        "top_repos": [
            {"name": r.get("name"), "description": r.get("description"), "language": r.get("language"),
             "stars": r.get("stargazers_count", 0)}
            for r in sorted(non_fork_repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:5]
        ],
        "profile_complete": profile_complete,
    }


def extract_from_linkedin_text(raw_text: str) -> dict:
    """LinkedIn does not offer a public scraping API; the prototype
    accepts pasted profile text (headline / about / experience / skills
    sections copied by the user) and classifies it the same way as a
    resume."""
    if not raw_text or not raw_text.strip():
        return {"source": "linkedin", "skills": [], "certifications": [], "education": [],
                 "profile_complete": False, "raw_text_length": 0}

    skills = _find_skills(raw_text)
    certifications = _find_certifications(raw_text)
    education = _find_education(raw_text)
    headline_match = re.search(r"^(.*)$", raw_text.strip().split("\n")[0])
    headline = headline_match.group(1) if headline_match else ""

    profile_complete = len(raw_text.strip()) > 200 and len(skills) > 0

    return {
        "source": "linkedin",
        "headline": headline[:200],
        "skills": skills,
        "certifications": certifications,
        "education": education,
        "profile_complete": profile_complete,
        "raw_text_length": len(raw_text),
    }
