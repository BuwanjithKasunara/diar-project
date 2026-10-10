"""Bounded, anonymous review of allowlisted current public repository text files."""
import base64
import binascii
import json
import re
import time
from urllib.parse import quote
import requests
from . import privacy_assessment as privacy

MAX_REPOSITORIES = 5
MAX_FILES_PER_REPOSITORY = 3
MAX_FILE_BYTES = 100 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
MAX_REQUESTS = 25
MAX_RESPONSE_BYTES = 256 * 1024
REQUEST_TIMEOUT = 5
SCAN_SECONDS = 20
SHA = re.compile(r"[a-fA-F0-9]{40}")
NAME = re.compile(r"[A-Za-z0-9_.-]+")
README_NAMES = ("readme.md", "readme.markdown", "readme.rst", "readme.txt", "readme")
LIMITS = {"repositories": MAX_REPOSITORIES, "files_per_repository": MAX_FILES_PER_REPOSITORY,
          "file_bytes": MAX_FILE_BYTES, "total_decoded_bytes": MAX_TOTAL_BYTES,
          "requests": MAX_REQUESTS, "response_bytes": MAX_RESPONSE_BYTES,
          "request_timeout_seconds": REQUEST_TIMEOUT, "elapsed_budget_seconds": SCAN_SECONDS}


def safe_label(value):
    text = value if isinstance(value, str) else ""
    return privacy._masked_text(text, privacy._matches(text, "name"))[0][:160]


def empty_result(enabled=False, status="disabled"):
    return {"evidence": [], "findings_count": 0, "coverage": {
        "enabled": enabled, "status": status, "repositories_available": 0,
        "repositories_selected": 0, "repositories_checked": 0, "files_checked": 0,
        "requests_used": 0, "decoded_bytes": 0, "limits": dict(LIMITS),
        "repositories": [], "selection": "First fetched public repositories, including forks; root allowlisted files only.",
    }}


class ScanIssue(Exception):
    """Application-generated reason only; never expose HTTP/file response text."""


class Budget:
    def __init__(self, deadline):
        self.deadline = deadline
        self.requests = 0
        self.decoded_bytes = 0
        self.stop_reason = None

    def check(self):
        if self.stop_reason:
            raise ScanIssue(self.stop_reason)
        if time.monotonic() >= self.deadline:
            self.stop_reason = "elapsed_budget"
            raise ScanIssue(self.stop_reason)

    def get_json(self, session, path):
        self.check()
        if self.requests >= MAX_REQUESTS:
            self.stop_reason = "request_budget"
            raise ScanIssue(self.stop_reason)
        self.requests += 1
        # Split remaining time across connection/read; check the elapsed budget
        # before and after streamed chunks. No redirects, auth, retries or raw URLs.
        request_deadline = min(self.deadline, time.monotonic() + REQUEST_TIMEOUT)
        timeout = max(0.001, (request_deadline - time.monotonic()) / 2)
        def check_request():
            self.check()
            if time.monotonic() >= request_deadline:
                raise ScanIssue("request_timeout")
        try:
            with session.get("https://api.github.com" + path, headers={"Accept": "application/vnd.github+json"},
                             timeout=timeout, stream=True, allow_redirects=False) as response:
                check_request()
                if response.status_code in (403, 429):
                    self.stop_reason = "rate_limited_or_denied"
                    raise ScanIssue(self.stop_reason)
                if response.status_code != 200:
                    raise ScanIssue("http_" + str(response.status_code))
                length = response.headers.get("Content-Length")
                if length and int(length) > MAX_RESPONSE_BYTES:
                    raise ScanIssue("response_too_large")
                body = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    check_request()
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ScanIssue("response_too_large")
                    body.extend(chunk)
                check_request()
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ScanIssue("invalid_response")
                return data
        except requests.Timeout:
            raise ScanIssue("request_timeout") from None
        except requests.RequestException:
            raise ScanIssue("request_failed") from None
        except (ValueError, UnicodeError):
            raise ScanIssue("invalid_response") from None


def scan_public_files(repositories, overall_deadline=None):
    result = empty_result(True, "unavailable")
    coverage = result["coverage"]
    repositories = repositories if isinstance(repositories, list) else []
    coverage["repositories_available"] = len(repositories)
    coverage["repositories_selected"] = min(MAX_REPOSITORIES, len(repositories))
    deadline = time.monotonic() + SCAN_SECONDS
    if overall_deadline is not None:
        deadline = min(deadline, overall_deadline)
    budget = Budget(deadline)
    incomplete = len(repositories) > MAX_REPOSITORIES
    # trust_env=False prevents .netrc credentials and environment auth/proxies
    # from expanding the anonymous public-only collection scope.
    with requests.Session() as session:
        session.trust_env = False
        for repo_index, repo in enumerate(repositories[:MAX_REPOSITORIES]):
            if not isinstance(repo, dict):
                repo = {}
            record = {"repository_name": safe_label(repo.get("name")), "status": "unavailable", "files": []}
            coverage["repositories"].append(record)
            try:
                budget.check()
                # Require an explicit public API result, rather than trusting an URL.
                full_name = repo.get("full_name", "")
                parts = full_name.split("/") if isinstance(full_name, str) else []
                if repo.get("private") is not False or len(parts) != 2 or not all(NAME.fullmatch(part) and part not in (".", "..") for part in parts):
                    raise ScanIssue("not_verified_public_repository")
                branch = repo.get("default_branch")
                if not isinstance(branch, str) or not branch or len(branch) > 255:
                    raise ScanIssue("missing_default_branch")
                base = "/repos/" + "/".join(quote(part, safe="") for part in parts)
                ref = budget.get_json(session, base + "/git/ref/heads/" + quote(branch, safe=""))
                obj = ref.get("object", {})
                revision = obj.get("sha") if isinstance(obj, dict) else None
                if not isinstance(revision, str) or not SHA.fullmatch(revision) or obj.get("type") != "commit":
                    raise ScanIssue("invalid_revision")
                commit = budget.get_json(session, base + "/git/commits/" + revision)
                tree_obj = commit.get("tree", {})
                tree_sha = tree_obj.get("sha") if isinstance(tree_obj, dict) else None
                if not isinstance(tree_sha, str) or not SHA.fullmatch(tree_sha):
                    raise ScanIssue("invalid_tree")
                tree = budget.get_json(session, base + "/git/trees/" + tree_sha)
                entries = tree.get("tree")
                if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
                    raise ScanIssue("invalid_tree")
                record["revision"] = revision
                record["status"] = "checked"
                coverage["repositories_checked"] += 1
                if tree.get("truncated"):
                    incomplete = True
                    record["status"] = "partial"
                    record["reason"] = "root_tree_truncated"
                candidates = []
                for entry in entries:
                    path = entry.get("path")
                    if not isinstance(path, str) or "/" in path or "\\" in path:
                        continue
                    lower = path.lower()
                    if lower in README_NAMES or lower in ("contributing.md", "security.md"):
                        candidates.append(entry)
                # Prefer one README format, then contributing/security; no recursive discovery.
                candidates.sort(key=lambda item: (README_NAMES.index(item["path"].lower()) if item["path"].lower() in README_NAMES else 10 if item["path"].lower() == "contributing.md" else 11, item["path"]))
                selected = []
                readme_selected = False
                for entry in candidates:
                    is_readme = entry["path"].lower() in README_NAMES
                    if is_readme and readme_selected:
                        record["files"].append({"path": safe_label(entry["path"]), "status": "skipped", "reason": "alternate_readme"})
                        incomplete = True
                        continue
                    readme_selected |= is_readme
                    selected.append(entry)
                if not any(item["path"].lower() in README_NAMES for item in candidates):
                    record["files"].append({"path": "README", "status": "not_found"})
                for entry in selected[MAX_FILES_PER_REPOSITORY:]:
                    record["files"].append({"path": safe_label(entry["path"]), "status": "skipped", "reason": "file_limit"})
                    incomplete = True
                    record["status"] = "partial"
                for expected in ("contributing.md", "security.md"):
                    if not any(item["path"].lower() == expected for item in candidates):
                        record["files"].append({"path": expected, "status": "not_found"})
                for file_index, entry in enumerate(selected[:MAX_FILES_PER_REPOSITORY]):
                    file_record = {"path": safe_label(entry["path"]), "status": "skipped"}
                    record["files"].append(file_record)
                    try:
                        budget.check()
                        if entry.get("type") != "blob" or entry.get("mode") not in ("100644", "100755"):
                            raise ScanIssue("not_regular_file")
                        size = entry.get("size")
                        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or size > MAX_FILE_BYTES:
                            raise ScanIssue("file_too_large_or_unknown")
                        if budget.decoded_bytes + size > MAX_TOTAL_BYTES:
                            budget.stop_reason = "decoded_byte_budget"
                            raise ScanIssue(budget.stop_reason)
                        sha = entry.get("sha")
                        if not isinstance(sha, str) or not SHA.fullmatch(sha):
                            raise ScanIssue("invalid_blob")
                        blob = budget.get_json(session, base + "/git/blobs/" + sha)
                        content = blob.get("content")
                        if blob.get("encoding") != "base64" or not isinstance(content, str):
                            raise ScanIssue("unsupported_encoding")
                        encoded = "".join(content.split())
                        if len(encoded) > 4 * ((size + 2) // 3):
                            raise ScanIssue("size_mismatch")
                        padding = len(encoded) - len(encoded.rstrip("="))
                        if len(encoded) % 4 or len(encoded) // 4 * 3 - padding != size:
                            raise ScanIssue("size_mismatch")
                        raw = base64.b64decode(encoded, validate=True)
                        budget.decoded_bytes += len(raw)
                        if len(raw) != size or len(raw) > MAX_FILE_BYTES:
                            raise ScanIssue("size_mismatch")
                        text = raw.decode("utf-8-sig", errors="strict")
                        if any(ord(character) < 32 and character not in "\n\r\t" for character in text):
                            raise ScanIssue("binary_content")
                        budget.check()
                        findings, count = privacy._scan_field(text, "github_repository_file", safe_label(entry["path"]),
                                                             "observed_public", f"github-file-{repo_index + 1}-{file_index + 1}",
                                                             max(0, privacy.MAX_FINDINGS - len(result["evidence"])))
                        for item in findings:
                            item.update({"repository_name": record["repository_name"], "file_path": file_record["path"], "revision": revision})
                        result["evidence"].extend(findings)
                        result["findings_count"] += count
                        coverage["files_checked"] += 1
                        file_record.update({"status": "checked", "findings_count": count})
                    except (UnicodeError, binascii.Error):
                        file_record["reason"] = "unsupported_text_encoding"
                        incomplete = True
                        record["status"] = "partial"
                    except ScanIssue as issue:
                        file_record["reason"] = str(issue)
                        incomplete = True
                        record["status"] = "partial"
                if not selected:
                    record["status"] = "no_supported_files"
            except ScanIssue as issue:
                record["reason"] = str(issue)
                incomplete = True
    coverage.update({"requests_used": budget.requests, "decoded_bytes": budget.decoded_bytes,
                     "findings_count": result["findings_count"], "stop_reason": budget.stop_reason})
    if coverage["files_checked"]:
        coverage["status"] = "partial" if incomplete else "checked"
    elif coverage["repositories_checked"]:
        coverage["status"] = "partial" if incomplete else "no_supported_files"
    return result
