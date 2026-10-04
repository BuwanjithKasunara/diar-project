"""Conservative evidence-preserving extraction; no neural model is claimed."""
import difflib
import base64
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import fitz
import requests
from .. import config

SKILLS_DICT = json.loads((Path(__file__).parents[1] / "data/skills_dictionary.json").read_text())
ALIASES = {a.strip().lower(): c for group in SKILLS_DICT.values()
           for c, aliases in group.items() for a in [c, *aliases]}
PATTERNS = [(a, c, re.compile(r"(?<![\w+#])" + re.escape(a) + r"(?![\w+#])", re.I))
            for a, c in sorted(ALIASES.items(), key=lambda p: (-len(p[0]), p[0]))]
AMBIGUOUS = {"go", "rest", "cv", "r", "py", "ts", "ann", "pm", "node", "express", "react", "swift"}
TECH = re.compile(r"\b(skills?|technologies|languages?|frameworks?|programming|developed|implemented|built|using|coded|proficient)\b", re.I)
NEGATED = re.compile(r"\b(no|not|never|without|lack|lacking|unfamiliar)\b", re.I)
PLANNED = re.compile(r"\b(plan|planning|want|wish|hope|intend|studying|learn)\b", re.I)
UNCERTAIN = re.compile(r"\b(maybe|possibly|unsure|might)\b", re.I)
CONTACT = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\d)\+?\d[\d ()-]{8,}\d(?!\d)")

TEXT_STRENGTH = 0.8
README_STRENGTH = 1.0
METADATA_STRENGTH = 0.6
GITHUB_LANGUAGE_MAP = {
    "c": "c", "c++": "c++", "c#": "c#", "cuda": "cuda", "go": "go", "java": "java",
    "javascript": "javascript", "kotlin": "kotlin", "matlab": "matlab", "php": "php",
    "python": "python", "r": "r", "ruby": "ruby", "rust": "rust", "scala": "scala",
    "swift": "swift", "typescript": "typescript", "dockerfile": "docker",
}
ARTIFACT_TYPES = {
    "resume_text": "resume", "linkedin_text": "linkedin", "profile_bio": "bio",
    "repository_description": "description", "repository_topic": "topic",
    "repository_readme": "readme", "repository_language": "language",
    "repository_name": "name", "text": "text",
}


def status(value, reason=None):
    return {"status": value, "reason": reason}


def _with_provenance(item, origin, repository, strength):
    item = {
        **item,
        "origin": origin,
        "artifact_type": ARTIFACT_TYPES.get(origin, "text"),
        "repository": repository,
        "repository_locator": repository,
        "extraction_method": item["method"],
        "strength": round(strength, 3),
    }
    raw = "|".join(str(item.get(k) or "") for k in
                   ("skill", "source", "origin", "artifact_type", "repository_locator",
                    "excerpt", "extraction_method", "assertion"))
    item["id"] = "ev-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return item


def extract_evidence(text, source, origin=None, repository=None, strength=TEXT_STRENGTH, allow_typos=True):
    origin = origin or (source + "_text" if source in {"resume", "linkedin"} else "text")
    evidence = []
    for clause in re.split(r"\n|[;!?]|\.(?:\s|$)|\bbut\b", text, flags=re.I):
        clause = clause.strip()
        if not clause:
            continue
        context = re.sub(r"\b(machine|deep|reinforcement) learning\b", "technical subject", clause, flags=re.I)
        assertion = ("negated" if NEGATED.search(context) else "planned" if PLANNED.search(context)
                     else "uncertain" if UNCERTAIN.search(clause) else "claimed")
        covered = set()
        for alias, skill, pattern in PATTERNS:
            if alias in AMBIGUOUS and not TECH.search(clause):
                continue
            for match in pattern.finditer(clause):
                if any(i in covered for i in range(match.start(), match.end())):
                    continue
                covered.update(range(match.start(), match.end()))
                evidence.append(_with_provenance(
                    dict(skill=skill, source=source, excerpt=clause[:300],
                         method="exact" if alias == skill else "alias", assertion=assertion),
                    origin, repository, strength))
        # Typo matching is limited to comma-separated explicit skill lists.
        if allow_typos and re.match(r"^(?:technical )?(?:skills|technologies|languages)\s*:", clause, re.I) and assertion == "claimed":
            for item in re.split(r",|/|\band\b", clause.split(":", 1)[1], flags=re.I):
                item = item.strip().lower()
                if not re.fullmatch(r"[a-z][a-z+#-]{3,}", item) or item in ALIASES:
                    continue
                candidates = [a for a in ALIASES if " " not in a and a not in AMBIGUOUS and a[0] == item[0]]
                matches = difflib.get_close_matches(item, candidates, n=1, cutoff=0.82)
                if matches:
                    evidence.append(_with_provenance(
                        dict(skill=ALIASES[matches[0]], source=source, excerpt=clause[:300],
                             method="typo", assertion="claimed"), origin, repository, min(strength, 0.5)))
    unique = {(e["skill"], e["source"], e["origin"], e.get("repository"), e["excerpt"],
               e["method"], e["assertion"]): e for e in evidence}
    return [unique[k] for k in sorted(unique)]


def _find_skills(text, fuzzy=True):
    return sorted({e["skill"] for e in extract_evidence(text, "text")
                   if e["assertion"] == "claimed" and (fuzzy or e["method"] != "typo")})


def sections(text):
    parts = {"other": []}
    active = "other"
    for line in text.splitlines():
        match = re.match(r"^\s*(work experience|professional experience|employment|experience|education|projects|portfolio|skills|certifications)\s*(?::|$)(.*)", line, re.I)
        if match:
            key = match[1].lower()
            active = "experience" if key in {"employment", "work experience", "professional experience", "experience"} else key
            parts.setdefault(active, []).append(match[2])
        else:
            parts.setdefault(active, []).append(line)
    return {k: "\n".join(v).strip() for k, v in parts.items()}


def experience_years(text, today=None):
    today = today or date.today()
    work = sections(text).get("experience", "")
    if not work:
        return None
    intervals = []
    pattern = r"\b((?:19|20)\d{2})(?:-(\d{2}))?\s*(?:-|–|—|\bto\b)\s*((?:19|20)\d{2}|present|current)(?:-(\d{2}))?\b"
    for match in re.finditer(pattern, work, re.I):
        sy, sm, ey, em = match.groups()
        try:
            start = date(int(sy), int(sm or 1), 1)
            end = today if not ey.isdigit() else date(int(ey), int(em or 1), 1)
        except ValueError:
            return None
        if end < start or start > today or end > today:
            return None
        intervals.append((start, end))
    if not intervals:
        return None
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return round(sum((end-start).days for start, end in merged) / 365.25, 1)


def extract_text(text, source, visibility="private"):
    evidence = extract_evidence(text, source)
    parts = sections(text)
    present = bool(text.strip())
    project_text = parts.get("projects", "") or parts.get("portfolio", "")
    if not project_text:
        inline_projects = re.search(r"\b(?:projects?|portfolio)\s*:\s*(.+)", text, re.I | re.S)
        if inline_projects:
            project_text = inline_projects.group(1).strip()
    return {
        "source": source, "source_status": status("analysed" if present else "not_supplied"),
        "skills": sorted({e["skill"] for e in evidence if e["assertion"] == "claimed"}),
        "evidence": evidence,
        "certifications": sorted({line.strip() for line in text.splitlines()
                                   if re.search(r"\b(certified|certificate|certification|credential)\b", line, re.I)
                                   and not NEGATED.search(line)}),
        "education": sorted({line.strip() for line in text.splitlines()
                              if re.search(r"\b(bachelor|master|degree|university|diploma|phd)\b", line, re.I)}),
        "experience_snippet": parts.get("experience", "")[:1500],
        "projects_snippet": project_text[:1500],
        "estimated_years_experience": experience_years(text),
        "raw_text_length": len(text), "headline": text.strip().split("\n")[0][:200],
        "profile_complete": present and len(parts) > 2,
        "contact_info_detected": bool(CONTACT.search(text)), "visibility": visibility,
    }


def extract_from_resume_text(raw_text):
    return extract_text(raw_text, "resume")


def extract_from_linkedin_text(raw_text, visibility="unverified"):
    return extract_text(raw_text, "linkedin", visibility)


def extract_text_from_pdf(file_bytes):
    if len(file_bytes) > config.MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the configured byte limit.")
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            if doc.needs_pass:
                raise ValueError("Encrypted PDF: supply an unlocked copy.")
            if len(doc) > config.MAX_PDF_PAGES:
                raise ValueError("PDF exceeds the configured page limit.")
            text = "\n".join(page.get_text() for page in doc)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unreadable or invalid PDF.") from exc
    if not text.strip():
        raise ValueError("No readable text in PDF. Supply a text PDF; OCR is not supported.")
    return text


def _parse_github_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _as_of_datetime(as_of):
    if as_of is None:
        return datetime.now(timezone.utc)
    if isinstance(as_of, datetime):
        return as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
    if isinstance(as_of, date):
        return datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)
    raise TypeError("as_of must be a date or datetime.")


def _repo_name(repo):
    return str(repo.get("full_name") or repo.get("name") or "")


def _benchmark_skills(benchmark):
    if not benchmark:
        return set()
    capabilities = benchmark.get("capabilities") or []
    if capabilities:
        return {skill for capability in capabilities for skill in capability.get("skills", [])}
    return set(benchmark.get("required_skills", [])) | set(benchmark.get("preferred_skills", []))


def _repo_relevance(repo, benchmark):
    text = "\n".join([repo.get("name") or "", repo.get("description") or "",
                      " ".join(repo.get("topics") or [])])
    skills = set(_find_skills("Skills: " + text, fuzzy=False))
    accepted = _benchmark_skills(benchmark)
    keywords = benchmark.get("expected_project_keywords", []) if benchmark else []
    keyword_hits = sum(bool(re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", text, re.I)) for k in keywords)
    return len(skills & accepted) + keyword_hits


def _representative_repos(repos, benchmark, limit):
    candidates = [r for r in repos if not r.get("archived")]
    def pushed(repo):
        value = _parse_github_time(repo.get("pushed_at"))
        return value.timestamp() if value else 0
    relevance = sorted(candidates, key=lambda r: (-_repo_relevance(r, benchmark),
                       -int(r.get("stargazers_count") or 0), -pushed(r), _repo_name(r).lower()))
    chosen = relevance[:min(3, limit)]
    seen = {_repo_name(r).lower() for r in chosen}
    recent = sorted(candidates, key=lambda r: (-pushed(r), _repo_name(r).lower()))
    for repo in recent:
        if len(chosen) >= limit:
            break
        if _repo_name(repo).lower() not in seen:
            chosen.append(repo)
            seen.add(_repo_name(repo).lower())
    return chosen


def _readme_text(response):
    value = getattr(response, "text", None)
    if isinstance(value, str) and value:
        return value
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("content"), str):
        raise ValueError("Malformed GitHub README response.")
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"], validate=False).decode("utf-8", errors="replace")
    return data["content"]


def _metadata_evidence(skill, excerpt, repository):
    return _with_provenance({"skill": skill, "source": "github", "excerpt": excerpt[:300],
                             "method": "metadata", "assertion": "claimed"},
                            "repository_language", repository, METADATA_STRENGTH)


def extract_from_github(username, github_token=None, benchmark=None, as_of=None):
    result = {"source": "github", "username": username, "skills": [], "evidence": [],
              "languages": [], "repo_count": None, "recently_active_repo_count": None,
              "recently_pushed_owned_repo_count": None, "last_owned_repository_push_at": None,
              "profile_complete": False, "top_repos": [], "visibility": "public"}
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = github_token or config.GITHUB_TOKEN
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos, profile, readmes = [], None, {}
    reasons = []
    repo_inventory_complete = True
    try:
        with requests.Session() as session:
            response = session.get(f"https://api.github.com/users/{username}", headers=headers, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"GitHub profile request returned HTTP {response.status_code}.")
            profile = response.json()
            if not isinstance(profile, dict) or not profile.get("login"):
                profile = None
                raise ValueError("Malformed GitHub profile response.")
            for page in range(1, (config.MAX_REPOS + 99)//100 + 1):
                response = session.get(f"https://api.github.com/users/{username}/repos",
                                       params={"per_page": 100, "sort": "pushed", "type": "owner", "page": page},
                                       headers=headers, timeout=10)
                if response.status_code != 200:
                    raise ValueError(f"GitHub repositories request returned HTTP {response.status_code}.")
                batch = response.json()
                if not isinstance(batch, list) or any(not isinstance(r, dict) or
                    any(r.get(k) is not None and not isinstance(r[k], str)
                        for k in ("name", "full_name", "description", "language", "pushed_at")) or
                    (r.get("topics") is not None and not isinstance(r["topics"], list)) for r in batch):
                    raise ValueError("Malformed GitHub repositories response.")
                remaining = config.MAX_REPOS - len(repos)
                repos.extend(batch[:remaining])
                links = getattr(response, "links", {}) or {}
                if len(batch) > remaining or (len(repos) >= config.MAX_REPOS and
                                               (links.get("next") or len(batch) == 100)):
                    repo_inventory_complete = False
                    reasons.append("Repository cap reached; repository counts and recency are not assessed.")
                    break
                if len(batch) < 100:
                    break
            own = [r for r in repos if not r.get("fork")]
            selected = (_representative_repos(own, benchmark, config.MAX_GITHUB_READMES)
                        if benchmark is not None else [])
            for repo in selected:
                name = repo.get("name")
                if not name:
                    continue
                try:
                    readme_headers = {**headers, "Accept": "application/vnd.github.raw+json"}
                    response = session.get(f"https://api.github.com/repos/{username}/{name}/readme",
                                           headers=readme_headers, timeout=10)
                    if response.status_code == 404:
                        continue
                    if response.status_code != 200:
                        reasons.append(f"README for {_repo_name(repo)} returned HTTP {response.status_code}.")
                        continue
                    readmes[_repo_name(repo)] = _readme_text(response)[:config.MAX_GITHUB_README_CHARS]
                except (requests.RequestException, ValueError, TypeError):
                    reasons.append(f"README for {_repo_name(repo)} could not be analysed.")
    except (requests.RequestException, ValueError, TypeError) as exc:
        if profile is not None:
            repo_inventory_complete = False
        reasons.append(str(exc) if isinstance(exc, ValueError) else "GitHub connection failed; retry later.")
    reason = " ".join(dict.fromkeys(reasons)) or None
    if profile is None:
        result.update(source_status=status("failed", reason), error=reason)
        return result

    own = [r for r in repos if not r.get("fork")]
    evidence = extract_evidence(profile.get("bio") or "", "github", "profile_bio", None, TEXT_STRENGTH,
                                allow_typos=False)
    project_text = []
    for repo in own:
        repository = _repo_name(repo)
        name = repo.get("name") or ""
        description = repo.get("description") or ""
        topics = [t for t in (repo.get("topics") or []) if isinstance(t, str)]
        evidence.extend(extract_evidence("Skills: " + name.replace("-", " ").replace("_", " "), "github",
                                         "repository_name", repository, METADATA_STRENGTH, allow_typos=False))
        evidence.extend(extract_evidence(description, "github", "repository_description", repository,
                                         TEXT_STRENGTH, allow_typos=False))
        evidence.extend(extract_evidence("Skills: " + ", ".join(topics), "github", "repository_topic",
                                         repository, METADATA_STRENGTH, allow_typos=False))
        if description:
            project_text.append(description)
        language = repo.get("language")
        canonical = GITHUB_LANGUAGE_MAP.get(language.lower()) if isinstance(language, str) else None
        if canonical:
            evidence.append(_metadata_evidence(canonical, f"Repository primary language: {language}", repository))
    for repository, readme in readmes.items():
        evidence.extend(extract_evidence(readme, "github", "repository_readme", repository,
                                         README_STRENGTH, allow_typos=False))
        project_text.append(readme[:2000])

    unique = {(e["skill"], e["source"], e["origin"], e.get("repository"), e["excerpt"],
               e["method"], e["assertion"]): e for e in evidence}
    evidence = [unique[k] for k in sorted(unique)]
    langs = sorted({r["language"].lower() for r in own if isinstance(r.get("language"), str)})
    cutoff = _as_of_datetime(as_of) - timedelta(days=config.ACTIVITY_DAYS)
    pushed_values = [_parse_github_time(r.get("pushed_at")) for r in own]
    invalid_dates = any(r.get("pushed_at") is not None and parsed is None for r, parsed in zip(own, pushed_values))
    if invalid_dates:
        repo_inventory_complete = False
        reason = " ".join(filter(None, [reason, "Some repository push dates were unavailable; recency is not assessed."]))
    valid_pushes = [value for value in pushed_values if value is not None]
    active = sum(value >= cutoff for value in valid_pushes)
    last_push = max(valid_pushes).isoformat() if valid_pushes else None
    counts_available = repo_inventory_complete and not invalid_dates
    result.update(source_status=status("partial" if reason else "analysed", reason), error=reason,
                  activity_window_days=config.ACTIVITY_DAYS,
                  activity_proxy="owned public non-fork repository push timestamps",
                  evidence=evidence, skills=sorted({e["skill"] for e in evidence if e["assertion"] == "claimed"}),
                  languages=langs, repo_count=len(own) if counts_available else None,
                  recently_active_repo_count=active if counts_available else None,
                  recently_pushed_owned_repo_count=active if counts_available else None,
                  last_owned_repository_push_at=last_push if counts_available else None,
                  bio=profile.get("bio"), followers=profile.get("followers", 0),
                  profile_complete=bool(profile.get("bio") and profile.get("name")),
                  contact_info_detected=bool(profile.get("email") or CONTACT.search(profile.get("bio") or "")),
                  projects_snippet="\n".join(project_text)[:10000],
                  top_repos=[{k: r.get(k) for k in ("name", "full_name", "description", "language", "topics")}
                             for r in _representative_repos(own, benchmark, config.MAX_GITHUB_READMES)])
    return result
