"""Apply the selected redaction policy to report text and metadata."""
import copy
import re
from typing import Optional


ANONYMOUS_USER = "[ANONYMOUS_USER]"
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d \t().-]{5,}\d(?!\w)")
DATE_OR_YEAR_RANGE = re.compile(r"(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{4}\s*[-–—]\s*\d{4})")
REPORT_POLICIES = ("mask_contacts", "mask_contacts_and_handle", "none")
LEGACY_POLICIES = {"Fully Public": "none", "Semi-Public": "mask_contacts", "Privacy Focused": "mask_contacts_and_handle"}


def effective_report_policy(report: dict, visibility_level: str) -> str:
    policy = report.get("report_metadata", {}).get("report_redaction")
    return policy if policy in REPORT_POLICIES else LEGACY_POLICIES.get(visibility_level, "mask_contacts")


def mask_contact_details(text: str) -> str:
    """Mask common email/phone formats, preserving ISO dates and year ranges."""
    def mask_phone(match):
        candidate = match.group().strip()
        digit_count = sum(character.isdigit() for character in candidate)
        prefix = match.string[max(0, match.start() - 40):match.start()]
        if (7 <= digit_count <= 15 and not DATE_OR_YEAR_RANGE.fullmatch(candidate)
                and not re.fullmatch(r"\d+(?:\.\d+){2,}", candidate)
                and not re.search(r"(?:version|build|id|ticket|stars?|followers?|commits?|count)\s*[:=#]?\s*$", prefix, re.I)):
            return "[REDACTED_PHONE]"
        return match.group()

    return PHONE_PATTERN.sub(mask_phone, EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text))


def contains_contact_details(text: str) -> bool:
    return mask_contact_details(text) != text


def sanitize_github_username(username: Optional[str], visibility_level: str) -> Optional[str]:
    if not username or not username.strip():
        return None
    if visibility_level == "Privacy Focused":
        return ANONYMOUS_USER
    return mask_contact_details(username.strip()) if visibility_level == "Semi-Public" else username.strip()


def sanitize_report_for_visibility(report: dict, visibility_level: str,
                                   github_username: Optional[str] = None) -> dict:
    """Compatibility mapping for callers/rows using the former visibility policy."""
    return sanitize_report(report, LEGACY_POLICIES.get(visibility_level, "mask_contacts"), github_username)


def sanitize_report(report: dict, report_redaction: str = "mask_contacts",
                    github_username: Optional[str] = None) -> dict:
    """Return a copy with the same redaction policy applied to every text field.

    The mask_contacts_and_handle policy also masks username fields and references to the known
    GitHub account in handles, quoted identifiers, and GitHub URLs. This is
    pattern-based redaction; names and identifying prose may still remain.
    """
    if report_redaction not in REPORT_POLICIES:
        raise ValueError("Unknown saved report protection policy")
    if report_redaction == "none":
        return copy.deepcopy(report)

    profile = report.get("digital_identity_profile", report)
    known_username = github_username or profile.get("github", {}).get("username")
    handle_pattern = None
    quoted_pattern = None
    github_url_pattern = None
    if report_redaction == "mask_contacts_and_handle" and known_username and not known_username.startswith("["):
        escaped_username = re.escape(known_username.strip())
        handle_pattern = re.compile(r"(?<![\w@])@" + escaped_username + r"(?![\w-])", re.I)
        quoted_pattern = re.compile(r"(['\"])" + escaped_username + r"\1", re.I)
        github_url_pattern = re.compile(
            r"(?:https?://)?(?:www\.)?github\.com/" + escaped_username
            + r"(?![\w-])(?:/[^\s<>\"']*)?", re.I
        )

    def redact(value, key=None):
        if isinstance(value, dict):
            return {item_key: redact(item_value, item_key) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, str):
            if report_redaction == "mask_contacts_and_handle" and key in ("username", "github_username") and value:
                return ANONYMOUS_USER
            text = mask_contact_details(value)
            if handle_pattern is not None:
                text = github_url_pattern.sub("[REDACTED_GITHUB_URL]", text)
                text = handle_pattern.sub(ANONYMOUS_USER, text)
                text = quoted_pattern.sub(lambda match: match.group(1) + ANONYMOUS_USER + match.group(1), text)
            return text
        return value

    return redact(report)
