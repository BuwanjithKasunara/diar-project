"""Conservative evidence-preserving extraction; no neural model is claimed."""
import difflib
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


def status(value, reason=None):
    return {"status": value, "reason": reason}


def extract_evidence(text, source):
    evidence = []
    for clause in re.split(r"\n|[;!?]|\.(?:\s|$)|\bbut\b", text, flags=re.I):
        clause = clause.strip()
        if not clause:
            continue
        assertion = ("negated" if NEGATED.search(clause) else "planned" if PLANNED.search(clause)
                     else "uncertain" if UNCERTAIN.search(clause) else "claimed")
        covered = set()
        for alias, skill, pattern in PATTERNS:
            if alias in AMBIGUOUS and not TECH.search(clause):
                continue
            for match in pattern.finditer(clause):
                if any(i in covered for i in range(match.start(), match.end())):
                    continue
                covered.update(range(match.start(), match.end()))
                evidence.append(dict(skill=skill, source=source, excerpt=clause[:300],
                                     method="exact" if alias == skill else "alias", assertion=assertion))
        # Typo matching is limited to comma-separated explicit skill lists.
        if re.match(r"^(?:technical )?(?:skills|technologies|languages)\s*:", clause, re.I) and assertion == "claimed":
            for item in re.split(r",|/|\band\b", clause.split(":", 1)[1], flags=re.I):
                item = item.strip().lower()
                if not re.fullmatch(r"[a-z][a-z+#-]{3,}", item) or item in ALIASES:
                    continue
                candidates = [a for a in ALIASES if " " not in a and a not in AMBIGUOUS and a[0] == item[0]]
                matches = difflib.get_close_matches(item, candidates, n=1, cutoff=0.82)
                if matches:
                    evidence.append(dict(skill=ALIASES[matches[0]], source=source, excerpt=clause[:300],
                                         method="typo", assertion="claimed"))
    unique = {(e["skill"], e["source"], e["excerpt"], e["method"], e["assertion"]): e for e in evidence}
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
        "projects_snippet": (parts.get("projects", "") or parts.get("portfolio", ""))[:1500],
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


def extract_from_github(username, github_token=None):
    result = {"source": "github", "username": username, "skills": [], "evidence": [],
              "languages": [], "repo_count": None, "recently_active_repo_count": None,
              "profile_complete": False, "top_repos": [], "visibility": "public"}
    headers = {"Accept": "application/vnd.github+json"}
    token = github_token or config.GITHUB_TOKEN
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos, profile = [], None
    reason = None
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
                                       params={"per_page": 100, "sort": "pushed", "page": page}, headers=headers, timeout=10)
                if response.status_code != 200:
                    raise ValueError(f"GitHub repositories request returned HTTP {response.status_code}.")
                batch = response.json()
                if not isinstance(batch, list) or any(not isinstance(r, dict) for r in batch):
                    raise ValueError("Malformed GitHub repositories response.")
                remaining = config.MAX_REPOS - len(repos)
                repos.extend(batch[:remaining])
                if len(batch) > remaining or (len(repos) >= config.MAX_REPOS and (response.links.get("next") or len(batch) == 100)):
                    reason = "Repository cap reached; counts and activity are not assessed."
                    break
                if len(batch) < 100:
                    break
    except (requests.RequestException, ValueError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "GitHub connection failed; retry later."
    if profile is None:
        result.update(source_status=status("failed", reason), error=reason)
        return result
    own = [r for r in repos if not r.get("fork")]
    text = "\n".join([profile.get("bio") or "", *[(r.get("description") or "") for r in own]])
    langs = sorted({r["language"].lower() for r in own if isinstance(r.get("language"), str)})
    evidence = extract_evidence(text, "github")
    evidence.extend(dict(skill=ALIASES.get(l, l), source="github", excerpt=f"Repository primary language: {l}",
                         method="metadata", assertion="claimed") for l in langs)
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.ACTIVITY_DAYS)
    active = 0
    for repo in own:
        try:
            pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
            active += pushed >= cutoff
        except (KeyError, TypeError, ValueError):
            reason = reason or "Some repository push dates unavailable; activity is not assessed."
    result.update(source_status=status("partial" if reason else "analysed", reason), error=reason,
                  evidence=evidence, skills=sorted({e["skill"] for e in evidence if e["assertion"] == "claimed"}),
                  languages=langs, repo_count=len(own) if not reason else None,
                  recently_active_repo_count=active if not reason else None,
                  bio=profile.get("bio"), followers=profile.get("followers", 0),
                  profile_complete=bool(profile.get("bio") and profile.get("name")),
                  contact_info_detected=bool(profile.get("email") or CONTACT.search(text)),
                  projects_snippet="\n".join(r.get("description") or "" for r in own),
                  top_repos=[{k: r.get(k) for k in ("name", "description", "language")} for r in own[:5]])
    return result
