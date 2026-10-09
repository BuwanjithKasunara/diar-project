"""Collect masked exposure evidence and turn it into visibility findings/rules.

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
            **({"line_number": text.count("\n", 0, start) + 1} if source == "github_repository_file" else {}),
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


def collect_privacy_evidence(resume_text, linkedin_text, github_privacy_data=None, resume_publicly_shared=False, repository_file_data=None):
    """Combine full supplied texts with already masked GitHub evidence.

    A resume defaults to an application document and is not treated as a public
    exposure candidate unless the user declares it public. A LinkedIn paste has
    unknown audience, so its recommendations remain conditional.
    """
    collector = _EvidenceCollector()
    resume_supplied = isinstance(resume_text, str) and bool(resume_text.strip())
    linkedin_supplied = isinstance(linkedin_text, str) and bool(linkedin_text.strip())
    resume_status = "user_declared_public" if resume_publicly_shared else "application_document"
    if resume_publicly_shared:
        collector.add(resume_text, "resume", "supplied_text", resume_status, "resume")
    before_linkedin = collector.findings_count
    collector.add(linkedin_text, "linkedin", "supplied_text", "supplied_text_unknown_audience", "linkedin")
    linkedin_findings_count = collector.findings_count - before_linkedin
    github = github_privacy_data if github_privacy_data is not None else collect_github_privacy_data()
    remaining = MAX_FINDINGS - len(collector.evidence)
    collector.evidence.extend(copy.deepcopy(github["evidence"][:remaining]))
    collector.findings_count += github["findings_count"]
    coverage = copy.deepcopy(github["coverage"])
    coverage.update({
        "resume": {"status": resume_status if resume_supplied else "not_supplied",
                   "public_exposure_reviewed": bool(resume_publicly_shared and resume_supplied)},
        "linkedin": {"status": "supplied_text_only" if linkedin_supplied else "not_supplied",
                     "audience_verified": False, "findings_count": linkedin_findings_count},
    })
    limitations = list(github["limitations"])
    if repository_file_data is not None:
        file_coverage = copy.deepcopy(repository_file_data["coverage"])
        coverage["github_repository_files"] = file_coverage
        remaining = MAX_FINDINGS - len(collector.evidence)
        collector.evidence.extend(copy.deepcopy(repository_file_data["evidence"][:remaining]))
        collector.findings_count += repository_file_data["findings_count"]
        if file_coverage.get("enabled"):
            limitations = [text for text in limitations if text not in GITHUB_LIMITATIONS]
            limitations.extend([
                "GitHub metadata coverage is reported separately from the optional file review.",
                "The optional file review covers only listed root README, CONTRIBUTING.md and SECURITY.md files in selected fetched public repositories.",
                "Other files/folders, links, commit history, private repositories and account visibility settings were not inspected. Removing current file text does not remove historical copies.",
                "Public file contact details may describe examples or contributors; ownership and whether disclosure is unnecessary were not verified.",
            ])
    return collector.result(coverage, [*limitations,
        "LinkedIn review covers supplied text only; its audience and account settings were not verified.",
        "A resume is application information unless the user declares that it is publicly shared.",
        "Address and birth-date detection supports only explicit labels or a structured street-location field; unusual formats can be missed.",
    ])


SOURCE_LABELS = {
    "github_profile": "GitHub profile",
    "github_repository": "GitHub repository metadata",
    "github_repository_file": "public GitHub repository files",
    "linkedin": "LinkedIn text you supplied",
    "resume": "resume you marked publicly shared",
}
KIND_LABELS = {
    "email": "email address",
    "phone": "phone number",
    "street_address": "street address",
    "date_of_birth": "date of birth",
}


def _recommendation_for_group(source, kind, status, evidence):
    label = SOURCE_LABELS[source]
    kind_label = KIND_LABELS[kind]
    locations = sorted({item["location"] for item in evidence})
    location_label = ", ".join(locations)
    if source in ("github_repository", "github_repository_file"):
        names = sorted({item["repository_name"] for item in evidence if item.get("repository_name")})
        target = f"{label} ({', '.join(names)})" if names else label
    else:
        target = label

    if source == "github_repository_file":
        files = sorted({f"{item.get('repository_name', 'repository')} / {item.get('file_path', item['location'])}: line {item.get('line_number', '?')}" for item in evidence})
        reason = f"A {kind_label} pattern was found in current public file contents ({'; '.join(files)}). It may belong to an example or contributor. Review whether it needs to be public; ownership was not verified."
        steps = ["Review the identified files and lines; confirm whether each match is real personal information.",
                 "Remove or replace unnecessary details while retaining a suitable professional contact route.",
                 "Editing the current file does not remove historical commits, forks or cached copies."]
    elif status == "supplied_text_unknown_audience":
        reason = (
            f"A {kind_label} pattern was found in the {label} ({location_label}). "
            "DIAR has not verified the profile's audience. If this detail is visible publicly "
            "and is not needed there, consider removing it or restricting its audience."
        )
        steps = ["Check the audience for this field on LinkedIn.",
                 "If it is public and unnecessary, remove it or restrict who can see it."]
    elif status == "user_declared_public":
        reason = (
            f"A {kind_label} pattern was found in the {label} ({location_label}). "
            "You indicated that this resume is public; DIAR has not verified where it is posted. "
            "Review the public copy and keep a recruitment contact route if you need one."
        )
        steps = ["Review the public copy of this resume.",
                 "Remove or replace unnecessary personal contact details while keeping a suitable recruitment contact route."]
    else:
        reason = (
            f"A {kind_label} pattern was found in {target} ({location_label}), which came from "
            "GitHub's public profile/repository metadata. Review that field and remove the detail "
            "or restrict the repository if it is unnecessary to share."
        )
        steps = [f"Review {location_label} in {target}.",
                 "Remove or restrict unnecessary personal details; keep a professional contact route if useful."]

    if any(item["detection_basis"] == "possible" for item in evidence):
        reason = "This is a possible phone-number match. " + reason
    priority = "high" if kind in ("street_address", "date_of_birth") else "medium"
    if kind == "phone" and status in ("observed_public", "user_declared_public") and not any(
            item["detection_basis"] == "possible" for item in evidence):
        priority = "high"
    action = f"review_public_exposure:{source}:{kind}"
    return {
        "id": f"R10-privacy-{source}-{kind}",
        "condition": f"public_exposure_candidate AND source='{source}' AND kind='{kind}'",
        "action": action,
        "priority": priority,
        "reason": reason,
        "category": "visibility",
        "source": source,
        "evidence_ids": [item["id"] for item in evidence],
        "suggested_steps": steps,
    }


def assess_visibility(privacy_evidence, visibility_level):
    """Produce source-specific advice and an honest, coverage-aware summary."""
    if visibility_level not in ("Fully Public", "Semi-Public", "Privacy Focused"):
        raise ValueError("Unknown visibility level")
    privacy_evidence = privacy_evidence or {}
    evidence = privacy_evidence.get("evidence", [])
    eligible = [item for item in evidence if item.get("recommendation_eligible")
                and item.get("exposure_status") != "application_document"]
    grouped = {}
    for item in eligible:
        key = (item.get("source"), item.get("kind"), item.get("exposure_status"))
        if key[0] in SOURCE_LABELS and key[1] in KIND_LABELS:
            grouped.setdefault(key, []).append(item)
    rules = [_recommendation_for_group(source, kind, status, items)
             for (source, kind, status), items in sorted(grouped.items())]

    coverage = privacy_evidence.get("coverage", {})
    findings = []
    if rules:
        findings.append(f"Found {len(eligible)} supported or possible exposure match(es) in the supplied/inspected data. Contact values are masked in these findings.")
    else:
        checked = any(coverage.get(source, {}).get("status") in ("checked", "limited", "supplied_text_only", "user_declared_public")
                      for source in ("github_profile", "github_repositories", "linkedin", "resume"))
        findings.append("No supported exposure patterns matched the inspected fields. This is not a complete privacy audit."
                        if checked else "Public profile exposure was not assessed because no public-profile data was available.")

    resume_status = coverage.get("resume", {}).get("status")
    if resume_status == "application_document":
        findings.append("Resume contact details were treated as job-application information, not public exposure.")
    linkedin_coverage = coverage.get("linkedin", {})
    if linkedin_coverage.get("status") == "supplied_text_only":
        displayed_linkedin = any(item.get("source") == "linkedin" for item in eligible)
        detected_linkedin = linkedin_coverage.get("findings_count")
        if detected_linkedin == 0 or (detected_linkedin is None and not displayed_linkedin
                                     and not privacy_evidence.get("omitted_findings_count", 0)):
            findings.append("No supported exposure patterns were found in the LinkedIn text supplied. Its audience and account settings were not verified.")
        elif not displayed_linkedin:
            findings.append("LinkedIn findings may be omitted by the report limit; no source-specific action is shown without its evidence. Its audience and account settings were not verified.")
    github_profile = coverage.get("github_profile", {}).get("status")
    github_repositories = coverage.get("github_repositories", {}).get("status")
    if github_profile not in ("checked",) or github_repositories not in ("checked",):
        limitations = []
        if github_profile not in ("checked",):
            limitations.append("GitHub profile fields were not checked")
        if github_repositories not in ("checked", "limited"):
            limitations.append("GitHub repository metadata was not checked")
        if limitations:
            findings.append("Coverage: " + "; ".join(limitations) + ".")
    if github_repositories == "limited":
        findings.append("Coverage: only fetched GitHub repository metadata was checked; more repositories may exist.")
    if privacy_evidence.get("omitted_findings_count", 0):
        findings.append(f"Only the first {len(evidence)} findings are included; {privacy_evidence['omitted_findings_count']} more were omitted from the report.")
    file_coverage = coverage.get("github_repository_files")
    if file_coverage and file_coverage.get("enabled"):
        findings.append(f"Public file review: {file_coverage['status']} · {file_coverage.get('files_checked', 0)} files checked in {file_coverage.get('repositories_checked', 0)} repository trees. See checked/skipped coverage; this is not a whole-repository audit.")
    return {"findings": findings, "rules": rules, "evidence": evidence,
            "coverage": coverage,
            "limitations": privacy_evidence.get("limitations", []),
            "supported_kinds": privacy_evidence.get("supported_kinds", list(SUPPORTED_KINDS)),
            "assessment_version": 2,
            "goal": "reduce_unnecessary_public_exposure"}
