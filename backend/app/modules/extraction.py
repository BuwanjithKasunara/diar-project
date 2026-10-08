"""
Information Extraction Module (Natural Language Processing)
-------------------------------------------------------------
Extracts structured professional attributes (skills, education,
experience, certifications, projects) from unstructured text sources:
resume PDFs, GitHub profile data, and pasted LinkedIn text.

Enhancements:
1. Context-Aware Skill Categorization:
   Distinguishes between:
   - Claimed Skills: Verified or explicitly stated active hands-on experience.
   - Planned Skills: Future learning intent (e.g. "plan to learn Docker").
   - Negated Skills: Explicit lack of experience (e.g. "no experience with Java").
   - Uncertain Skills: Beginner or low-confidence mentions (e.g. "basic familiarity with Kubernetes").

2. Frequency Normalization & Noise Suppression:
   Uses sublinear term frequency scaling with saturation capping to eliminate
   keyword stuffing and suppress weak, isolated noise.

3. Explicit Data Source State Tracking:
   Tracks source states: "not_supplied" | "partial" | "failed" | "analysed".

4. GitHub Recency & Domain Relevance:
   Calculates active commit recency (fresh vs moderate vs stale) and evaluates
   repository domain relevance against target technical competencies.
"""
import difflib
import json
import re
import os
import math
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from collections import defaultdict, Counter
import fitz  # PyMuPDF
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

with open(os.path.join(DATA_DIR, "skills_dictionary.json")) as f:
    SKILLS_DICT = json.load(f)

# Flatten {category: {canonical: [aliases]}} into lookup structures:
ALIAS_TO_CANONICAL = {}
for _category, _skills in SKILLS_DICT.items():
    for _canonical, _aliases in _skills.items():
        for _alias in _aliases:
            ALIAS_TO_CANONICAL[_alias.strip().lower()] = _canonical

ALL_ALIAS_PATTERNS = sorted(ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)
SINGLE_WORD_ALIASES = {a: c for a, c in ALIAS_TO_CANONICAL.items() if " " not in a.strip() and len(a.strip()) > 2}

CERT_KEYWORDS = ["certified", "certificate", "certification", "credential"]
EDU_KEYWORDS = ["bachelor", "master", "phd", "b.sc", "bsc", "msc", "m.sc", "degree",
                "university", "college", "diploma", "undergraduate", "graduate"]
EXPERIENCE_HEADER = re.compile(r"(work experience|professional experience|experience)", re.I)
PROJECT_HEADER = re.compile(r"(projects|portfolio)", re.I)
SKILLS_HEADER = re.compile(r"(technical skills|core competencies|skills)", re.I)

FUZZY_MATCH_CUTOFF = 0.82

# Contextual Regex Patterns for Negation, Future Plans, and Uncertainty
NEGATION_PATTERN = re.compile(
    r"\b(no|not|never|neither|without|lack(?:ing)?\s+of|haven't|have\s+not|hadn't|had\s+not|zero)\s+"
    r"(?:prior\s+|any\s+|much\s+|hands-on\s+|practical\s+)?(?:experience\s+(?:with|in)|knowledge\s+of|familiarity\s+with|exposure\s+to|background\s+in|skills?\s+in)?",
    re.I
)
DIRECT_NEGATION_PREFIX = re.compile(r"\b(no|not|without|never)\b", re.I)

PLAN_PATTERN = re.compile(
    r"\b(plan(?:ning|s)?\s+to|aim(?:ing|s)?\s+to|goal\s+is\s+to|interested\s+in|aspiring\s+to|"
    r"want(?:ing|s)?\s+to|hoping\s+to|looking\s+to|currently\s+learning|in\s+progress\s+learning|"
    r"will\s+learn|future\s+learning|eager\s+to\s+learn|seeking\s+to\s+learn)\b",
    re.I
)

CONTRAST_PATTERN = re.compile(r"\b(but|however|except|although|yet|instead|whereas)\b", re.I)

UNCERTAIN_PATTERN = re.compile(
    r"\b(basic|fundamental|rudimentary|elementary|beginner|entry[\s-]level|novice|minimal|"
    r"surface[\s-]level|limited|introductory)\s*(?:knowledge\s+of|understanding\s+of|familiarity\s+with|skills?\s+in|experience\s+with)?",
    re.I
)

AFTER_UNCERTAIN_PATTERN = re.compile(
    r"^\s*[\(\[]?\s*(?:basic|beginner|novice|elementary|learning|introductory|fundamentals?)\s*[\)\]]?",
    re.I
)


def extract_contextual_skills(text: str, fuzzy: bool = True) -> Dict[str, Any]:
    """
    Categorizes skills into explicit contextual states:
    - claimed: actively demonstrated / verified hands-on skills
    - planned: future intent or in-progress learning
    - negated: explicitly denied / ruled-out skills
    - uncertain: low-confidence or beginner mentions
    
    Also computes frequency counts and sublinear normalized weights.
    """
    text_lower = " " + re.sub(r"\s+", " ", text.lower()) + " "
    matched_spans: List[Tuple[int, int, str]] = []

    # Pass 1: exact alias matches
    for alias in ALL_ALIAS_PATTERNS:
        alias_clean = alias.strip()
        if not alias_clean:
            continue
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(alias_clean) + r"(?![a-zA-Z0-9])"
        for m in re.finditer(pattern, text_lower):
            matched_spans.append((m.start(), m.end(), ALIAS_TO_CANONICAL[alias]))

    # Pass 2: typo-tolerant fuzzy matches
    if fuzzy:
        already_covered = set()
        for start, end, _ in matched_spans:
            already_covered.update(range(start, end))

        words = list(re.finditer(r"[a-zA-Z][a-zA-Z0-9+#./-]{2,}", text_lower))
        candidate_pool = list(SINGLE_WORD_ALIASES.keys())
        for m in words:
            w_start, w_end = m.start(), m.end()
            if w_start in already_covered:
                continue
            word = m.group().strip(".")
            if word in SINGLE_WORD_ALIASES:
                matched_spans.append((w_start, w_end, SINGLE_WORD_ALIASES[word]))
                continue
            close = difflib.get_close_matches(word, candidate_pool, n=1, cutoff=FUZZY_MATCH_CUTOFF)
            if close:
                matched_spans.append((w_start, w_end, SINGLE_WORD_ALIASES[close[0]]))

    # Context analysis per occurrence
    skill_mention_types = defaultdict(list)
    freq = Counter()

    for start, end, canonical_name in matched_spans:
        freq[canonical_name] += 1
        window_before = text_lower[max(0, start - 80):start]
        clause_before = re.split(r"[.!?;:\n]", window_before)[-1].strip()
        window_after = text_lower[end:min(len(text_lower), end + 30)]
        clause_after = re.split(r"[.!?;:\n]", window_after)[0].strip()

        neg_m = NEGATION_PATTERN.search(clause_before) or DIRECT_NEGATION_PREFIX.search(clause_before)
        plan_m = PLAN_PATTERN.search(clause_before)
        unc_m = UNCERTAIN_PATTERN.search(clause_before) or AFTER_UNCERTAIN_PATTERN.search(clause_after)

        if neg_m and not CONTRAST_PATTERN.search(clause_before[neg_m.end():]):
            m_type = "negated"
        elif plan_m and not CONTRAST_PATTERN.search(clause_before[plan_m.end():]):
            m_type = "planned"
        elif unc_m:
            m_type = "uncertain"
        else:
            m_type = "claimed"

        skill_mention_types[canonical_name].append(m_type)

    claimed_set = set()
    planned_set = set()
    negated_set = set()
    uncertain_set = set()

    for skill, types in skill_mention_types.items():
        if "claimed" in types:
            claimed_set.add(skill)
        elif "uncertain" in types:
            uncertain_set.add(skill)
        elif "planned" in types:
            planned_set.add(skill)
        elif all(t == "negated" for t in types):
            negated_set.add(skill)

    # Sublinear frequency normalization: weight = 1.0 + ln(capped_count) * 0.4
    # Eliminates artificial signal amplification from repeated keywords
    normalized_weights = {}
    for skill, count in freq.items():
        capped = min(count, 5)
        normalized_weights[skill] = round(1.0 + (math.log(capped) * 0.4), 3) if capped > 1 else 1.0

    return {
        "claimed": sorted(claimed_set),
        "planned": sorted(planned_set),
        "negated": sorted(negated_set),
        "uncertain": sorted(uncertain_set),
        "frequency": dict(freq),
        "normalized_weights": normalized_weights,
    }


def _find_skills(text: str, fuzzy: bool = True) -> list:
    """
    Returns verified active skills (claimed + uncertain), excluding
    explicitly negated skills or planned-only skills.
    """
    extracted = extract_contextual_skills(text, fuzzy=fuzzy)
    return sorted(set(extracted["claimed"]) | set(extracted["uncertain"]))


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
    """Extracts structured attributes from raw resume text with source state tracking."""
    cleaned = (raw_text or "").strip()
    if not cleaned:
        source_state = "not_supplied"
    elif len(cleaned) < 80:
        source_state = "partial"
    else:
        source_state = "analysed"

    contextual = extract_contextual_skills(cleaned)
    certifications = _find_certifications(cleaned)
    education = _find_education(cleaned)
    experience_section = _extract_section(cleaned, EXPERIENCE_HEADER)
    projects_section = _extract_section(cleaned, PROJECT_HEADER)

    # Years-of-experience heuristic
    year_ranges = re.findall(r"(20\d{2}|19\d{2})\s*[-–—to]{1,4}\s*(20\d{2}|present|current)", cleaned, re.I)
    years_experience = 0
    current_year = datetime.now().year
    for start, end in year_ranges:
        try:
            start_y = int(start)
            end_y = current_year if not end.isdigit() else int(end)
            years_experience = max(years_experience, max(0, end_y - start_y))
        except ValueError:
            continue

    return {
        "source": "resume",
        "source_state": source_state,
        "skills": contextual["claimed"] + contextual["uncertain"],
        "contextual_skills": contextual,
        "certifications": certifications,
        "education": education,
        "experience_snippet": experience_section,
        "projects_snippet": projects_section,
        "estimated_years_experience": years_experience,
        "raw_text_length": len(cleaned),
    }


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


GITHUB_REPOSITORY_LIMIT = 100


def _github_failure(username: str, source_state: str, error: str) -> dict:
    """Return an explicit unavailable state, rather than an empty portfolio."""
    return {
        "source": "github",
        "source_state": source_state,
        "repository_state": source_state,
        "repository_coverage": "unavailable",
        "repositories_fetched_count": 0,
        "username": username or None,
        "error": error,
        "skills": [],
        "contextual_skills": extract_contextual_skills(""),
        "languages": [],
        "repo_count": 0,
        "recently_active_repo_count": 0,
        "moderate_repo_count": 0,
        "stale_repo_count": 0,
        "profile_complete": False,
    }


def extract_from_github(username: str, github_token: Optional[str] = None) -> dict:
    """
    Pulls public profile + repo data from the GitHub REST API.
    Evaluates repository recency (decay based on days elapsed) and domain relevance.
    """
    clean_user = (username or "").strip()
    if not clean_user:
        return _github_failure("", "not_supplied", "No GitHub username supplied")

    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    profile_url = f"https://api.github.com/users/{clean_user}"
    repos_url = f"https://api.github.com/users/{clean_user}/repos?per_page={GITHUB_REPOSITORY_LIMIT}&sort=updated"

    try:
        profile_resp = requests.get(profile_url, headers=headers, timeout=10)
    except requests.RequestException:
        return _github_failure(clean_user, "failed", "GitHub profile could not be retrieved; try again later.")

    if profile_resp.status_code == 404:
        return _github_failure(clean_user, "failed", f"GitHub user '{clean_user}' not found")
    if profile_resp.status_code in (403, 429):
        return _github_failure(clean_user, "failed", "GitHub API access was denied or rate limited; try again later.")
    if profile_resp.status_code != 200:
        return _github_failure(clean_user, "failed", f"GitHub profile request returned status {profile_resp.status_code}.")

    try:
        profile = profile_resp.json()
        if not isinstance(profile, dict):
            raise ValueError("Expected a GitHub profile object")
    except ValueError:
        return _github_failure(clean_user, "failed", "GitHub returned an unreadable profile response; try again later.")

    # Keep usable profile evidence even if the independent repository request fails.
    repos = []
    repository_state = "failed"
    repository_coverage = "unavailable"
    warning = None
    try:
        repos_resp = requests.get(repos_url, headers=headers, timeout=10)
        if repos_resp.status_code == 200:
            repos = repos_resp.json()
            if not isinstance(repos, list) or any(not isinstance(repo, dict) for repo in repos):
                raise ValueError("Expected a GitHub repository list")
            # One bounded request keeps the prototype responsive. Never imply that
            # this page represents the entire portfolio when another page exists.
            limited = bool(repos_resp.links.get("next")) or profile.get("public_repos", 0) > len(repos)
            repository_state = "partial" if limited else "analysed"
            repository_coverage = "limited" if limited else "complete"
            if limited:
                warning = (
                    f"GitHub analysis covers only the first {len(repos)} public repositories "
                    f"sorted by update time (limit {GITHUB_REPOSITORY_LIMIT}, including forks). "
                    "Repository count, activity, and language recommendations are withheld because coverage is incomplete."
                )
        else:
            warning = (
                f"GitHub profile loaded, but repository data could not be retrieved "
                f"(status {repos_resp.status_code}). "
                "Repository count, activity, and language recommendations are withheld. Try again later."
            )
    except ValueError:
        repos = []
        warning = (
            "GitHub profile loaded, but the repository response was unreadable. "
            "Repository count, activity, and language recommendations are withheld. Try again later."
        )
    except requests.RequestException:
        warning = (
            "GitHub profile loaded, but the repository request failed. "
            "Repository count, activity, and language recommendations are withheld. Try again later."
        )

    non_fork_repos = [r for r in repos if not r.get("fork")]

    # Dynamic Recency Analysis (days elapsed rather than static year)
    now = datetime.now(timezone.utc)
    fresh_repos = []
    moderate_repos = []
    stale_repos = []

    for r in non_fork_repos:
        pushed = r.get("pushed_at") or r.get("updated_at")
        if pushed:
            try:
                dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                days_old = (now - dt).days
                if days_old <= 365:
                    fresh_repos.append(r)
                elif days_old <= 730:
                    moderate_repos.append(r)
                else:
                    stale_repos.append(r)
            except Exception:
                fresh_repos.append(r)
        else:
            fresh_repos.append(r)

    languages = sorted({r.get("language") for r in non_fork_repos if r.get("language")})
    descriptions_text = " ".join([r.get("description") or "" for r in non_fork_repos])
    topic_text = " ".join([" ".join(r.get("topics", [])) for r in non_fork_repos if isinstance(r.get("topics"), list)])
    combined_text = f"{descriptions_text} {topic_text} {profile.get('bio') or ''}"
    contextual = extract_contextual_skills(combined_text)

    profile_complete = bool(profile.get("bio")) and bool(profile.get("name")) and len(non_fork_repos) > 0 and repository_state == "analysed"
    source_state = "analysed" if repository_state == "analysed" else "partial"

    return {
        "source": "github",
        "source_state": source_state,
        "repository_state": repository_state,
        "repository_coverage": repository_coverage,
        "repositories_fetched_count": len(repos),
        "error": warning,
        "username": clean_user,
        "name": profile.get("name"),
        "bio": profile.get("bio"),
        "public_repos": profile.get("public_repos", 0),
        "followers": profile.get("followers", 0),
        "repo_count": len(non_fork_repos),
        "recently_active_repo_count": len(fresh_repos),
        "moderate_repo_count": len(moderate_repos),
        "stale_repo_count": len(stale_repos),
        "languages": [l.lower() for l in languages],
        "skills": contextual["claimed"] + contextual["uncertain"],
        "contextual_skills": contextual,
        "top_repos": [
            {"name": r.get("name"), "description": r.get("description"), "language": r.get("language"),
             "stars": r.get("stargazers_count", 0)}
            for r in sorted(non_fork_repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:5]
        ],
        "profile_complete": profile_complete,
    }


def extract_from_linkedin_text(raw_text: str) -> dict:
    """Extracts attributes from pasted LinkedIn profile text with source state tracking."""
    cleaned = (raw_text or "").strip()
    if not cleaned:
        return {
            "source": "linkedin",
            "source_state": "not_supplied",
            "headline": "",
            "skills": [],
            "contextual_skills": {"claimed": [], "planned": [], "negated": [], "uncertain": [], "frequency": {}, "normalized_weights": {}},
            "certifications": [],
            "education": [],
            "profile_complete": False,
            "raw_text_length": 0,
        }

    source_state = "partial" if len(cleaned) < 100 else "analysed"
    contextual = extract_contextual_skills(cleaned)
    certifications = _find_certifications(cleaned)
    education = _find_education(cleaned)
    headline_match = re.search(r"^(.*)$", cleaned.split("\n")[0])
    headline = headline_match.group(1) if headline_match else ""

    profile_complete = len(cleaned) > 200 and len(contextual["claimed"]) > 0

    return {
        "source": "linkedin",
        "source_state": source_state,
        "headline": headline[:200],
        "skills": contextual["claimed"] + contextual["uncertain"],
        "contextual_skills": contextual,
        "certifications": certifications,
        "education": education,
        "profile_complete": profile_complete,
        "raw_text_length": len(cleaned),
    }
