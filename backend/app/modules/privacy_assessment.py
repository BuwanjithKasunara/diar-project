"""Collect masked exposure evidence; recommendation rules are added in Part 2.

This module does not change source text, career extraction, or report policies.
Pattern matches identify review candidates, not proof that information is unsafe.
"""
import copy
import re
from datetime import date


MAX_FINDINGS = 50
MAX_EXCERPT_LENGTH = 160
EXPOSURE_STATUSES = {
    "observed_public", "supplied_text_unknown_audience",
    "user_declared_public", "application_document",
}
SUPPORTED_KINDS = ["email", "phone", "street_address", "date_of_birth"]
EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE = re.compile(r"(?<![\w.+-])\+?\d[\d \t().-]{5,}\d(?![\w.+-])")
DATE_OR_RANGE = re.compile(r"(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{4}\s*[-–—]\s*\d{4})")
PHONE_LABEL = re.compile(r"(?:phone|telephone|tel|mobile|contact number)\s*[:=]?\s*$", re.I)
NON_PHONE_LABEL = re.compile(r"(?:version|release|build|id|ticket|issue|order|stars?|followers?|views?|downloads?|commits?|repositories|repos?|count|salary)\s*[:=#]?\s*$", re.I)
NON_PHONE_SUFFIX = re.compile(r"^\s*(?:stars?|followers?|views?|downloads?|commits?|repositories|repos?|years?|users?)\b", re.I)
ADDRESS = re.compile(r"\b(?:(?:home|street|postal|mailing)\s+)?address\s*:\s*([^\n;]{1,120})", re.I)
STREET = re.compile(r"\b\d+[A-Za-z]?(?:[/-]\d+)?\s+(?:[\w.'-]+\s+){1,6}(?:street|road|lane|avenue|drive|boulevard|st\.?|rd\.?|ln\.?|ave\.?)\b", re.I)
DOB = re.compile(r"\b(?:date of birth|dob|birth date)\s*[:=]\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})(?!\d)", re.I)
MARKERS = {"email": "[EMAIL]", "phone": "[PHONE]", "street_address": "[ADDRESS]", "date_of_birth": "[DOB]"}
GITHUB_LIMITATIONS = [
    "Only returned GitHub profile fields and fetched public repository metadata were inspected.",
    "Repository files, README files, commit history, private repositories and account visibility settings were not inspected.",
]


def _matches(text, location):
    matches = [(m.start(), m.end(), "email", "pattern") for m in EMAIL.finditer(text)]
    for match in PHONE.finditer(text):
        candidate = match.group().strip()
        digits = sum(c.isdigit() for c in candidate)
        prefix = text[max(0, match.start() - 40):match.start()]
        suffix = text[match.end():match.end() + 25]
        if not 7 <= digits <= 15 or DATE_OR_RANGE.fullmatch(candidate):
            continue
        # Dotted versions, labelled metrics/IDs and career totals are not phones.
        if re.fullmatch(r"\d+(?:\.\d+){2,}", candidate):
            continue
        if NON_PHONE_LABEL.search(prefix) or NON_PHONE_SUFFIX.search(suffix):
            continue
        certainty = "labelled" if PHONE_LABEL.search(prefix) else "possible"
        matches.append((match.start(), match.end(), "phone", certainty))
    for match in ADDRESS.finditer(text):
        if STREET.search(match.group(1)):
            matches.append((match.start(1), match.end(1), "street_address", "labelled"))
    # A structured public location field can provide address context itself.
    if location == "location" and STREET.search(text) and not any(item[2] == "street_address" for item in matches):
        matches.append((0, len(text), "street_address", "structured_field"))
    for match in DOB.finditer(text):
        value = match.group(1)
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                parsed = date.fromisoformat(value)
            else:
                day, month, year = map(int, re.split(r"[/-]", value))
                parsed = date(year, month, day)
        except ValueError:
            continue
        if date(1900, 1, 1) <= parsed <= date.today():
            matches.append((match.start(1), match.end(1), "date_of_birth", "labelled"))
    return sorted(matches)


def _masked_text(text, matches):
    """Mask full matches before cropping, including overlapping disclosures."""
    ranges = []
    for start, end, kind, _ in matches:
        if ranges and start < ranges[-1][1]:
            previous = ranges[-1]
            previous[1] = max(previous[1], end)
            previous[2] = "[PERSONAL_DETAIL]"
        else:
            ranges.append([start, end, MARKERS[kind]])
    parts, offsets, cursor, output_length = [], [], 0, 0
    for start, end, marker in ranges:
        plain = text[cursor:start]
        parts.extend([plain, marker])
        output_length += len(plain)
        offsets.append((start, end, output_length))
        output_length += len(marker)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), offsets


def _scan_field(text, source, location, exposure_status, evidence_prefix, limit):
    if exposure_status not in EXPOSURE_STATUSES:
        raise ValueError("Unknown exposure status")
    if not isinstance(text, str) or not text.strip():
        return [], 0
    matches = _matches(text, location)
    masked, offsets = _masked_text(text, matches)
    findings, seen, total = [], set(), 0
    for start, end, kind, certainty in matches:
        raw = text[start:end]
        key = (kind, re.sub(r"\D", "", raw) if kind == "phone" else raw.casefold().strip())
        if key in seen:
            continue
        seen.add(key)  # Transient; never returned or persisted.
        total += 1
        if len(findings) >= limit:
            continue
        offset = next(position for left, right, position in offsets if left <= start < right)
        excerpt_start = max(0, offset - 40)
        findings.append({
            "id": f"{evidence_prefix}-{kind}-{total}",
            "source": source,
            "location": location,
            "kind": kind,
            "exposure_status": exposure_status,
            "detection_basis": certainty,
            "display_evidence": masked[excerpt_start:excerpt_start + MAX_EXCERPT_LENGTH],
            "recommendation_eligible": exposure_status != "application_document",
        })
    return findings, total


def scan_text_for_exposure(text, source, location, exposure_status, evidence_prefix):
    """Return up to 50 masked, deduplicated candidates from one source field.

    Use the collectors when aggregate counts/coverage are needed. Prefix, source
    and location are application-generated labels, never personal identifiers.
    Unlabelled phone-like numbers are explicitly marked possible.
    """
    return _scan_field(text, source, location, exposure_status, evidence_prefix, MAX_FINDINGS)[0]


class _EvidenceCollector:
    def __init__(self):
        self.evidence = []
        self.findings_count = 0

    def add(self, text, source, location, status, prefix, repository_name=None):
        findings, count = _scan_field(text, source, location, status, prefix,
                                      MAX_FINDINGS - len(self.evidence))
        if repository_name is not None:
            name = repository_name if isinstance(repository_name, str) else ""
            safe_name, _ = _masked_text(name, _matches(name, "name"))
            for item in findings:
                item["repository_name"] = safe_name[:MAX_EXCERPT_LENGTH]
        self.evidence.extend(findings)
        self.findings_count += count

    def result(self, coverage, limitations):
        return {
            "evidence": self.evidence,
            "findings_count": self.findings_count,
            "omitted_findings_count": self.findings_count - len(self.evidence),
            "coverage": coverage,
            "supported_kinds": list(SUPPORTED_KINDS),
            "limitations": list(limitations),
        }


def collect_github_privacy_data(profile=None, repositories=None, profile_state="not_supplied",
                                repository_state="not_supplied", repository_coverage="unavailable"):
    """Review existing API responses, with no extra network calls.

    Includes forks for privacy review; career extraction remains independent.
    Successful metadata coverage says nothing about file contents/settings.
    """
    collector = _EvidenceCollector()
    checked_fields = []
    if isinstance(profile, dict):
        profile_state = "checked"
        for field in ("bio", "email", "location", "blog"):
            if field in profile:
                checked_fields.append(field)
                collector.add(profile[field], "github_profile", field, "observed_public", f"github-profile-{field}")
    repositories = repositories or []
    for index, repo in enumerate(repositories):
        for field in ("name", "description"):
            collector.add(repo.get(field), "github_repository", field, "observed_public",
                          f"github-repo-{index + 1}-{field}", repo.get("name"))
        topics = repo.get("topics", [])
        if isinstance(topics, list):
            for topic_index, topic in enumerate(topics):
                collector.add(topic, "github_repository", f"topics[{topic_index}]", "observed_public",
                              f"github-repo-{index + 1}-topic-{topic_index}", repo.get("name"))
    status = {"analysed": "checked", "partial": "limited"}.get(repository_state, repository_state)
    return collector.result({
        "github_profile": {"status": profile_state, "checked_fields": checked_fields},
        "github_repositories": {
            "status": status, "repositories_checked": len(repositories),
            "repository_coverage": repository_coverage, "checked_fields": ["name", "description", "topics"],
            "files_inspected": False,
        },
    }, GITHUB_LIMITATIONS)


def collect_privacy_evidence(resume_text, linkedin_text, github_privacy_data=None, resume_publicly_shared=False):
    """Combine full supplied texts with already masked GitHub evidence.

    This is a Part 1 foundation API, not yet wired into /api/analyze. A resume
    defaults to an application document; a LinkedIn paste has unknown audience.
    """
    collector = _EvidenceCollector()
    resume_supplied = isinstance(resume_text, str) and bool(resume_text.strip())
    linkedin_supplied = isinstance(linkedin_text, str) and bool(linkedin_text.strip())
    resume_status = "user_declared_public" if resume_publicly_shared else "application_document"
    collector.add(resume_text, "resume", "supplied_text", resume_status, "resume")
    collector.add(linkedin_text, "linkedin", "supplied_text", "supplied_text_unknown_audience", "linkedin")
    github = github_privacy_data if github_privacy_data is not None else collect_github_privacy_data()
    remaining = MAX_FINDINGS - len(collector.evidence)
    collector.evidence.extend(copy.deepcopy(github["evidence"][:remaining]))
    collector.findings_count += github["findings_count"]
    coverage = copy.deepcopy(github["coverage"])
    coverage.update({
        "resume": {"status": resume_status if resume_supplied else "not_supplied"},
        "linkedin": {"status": "supplied_text_only" if linkedin_supplied else "not_supplied", "audience_verified": False},
    })
    return collector.result(coverage, [*github["limitations"],
        "LinkedIn review covers supplied text only; its audience and account settings were not verified.",
        "A resume is application information unless the user declares that it is publicly shared.",
        "Address and birth-date detection supports only explicit labels or a structured street-location field; unusual formats can be missed.",
    ])
