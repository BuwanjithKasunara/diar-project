"""Synthetic API responses only: bounded collection, evidence, failures and invariants."""
import base64
import json
from unittest.mock import Mock
import pytest
import requests
from app.modules import repository_privacy as scan, privacy_assessment as privacy, extraction, ml_classifier
from app import database
from test_analysis_foundation import client as api, BASE

COMMIT, TREE, BLOB = "a" * 40, "b" * 40, "c" * 40
REPO = {"name": "repo", "full_name": "fixture/repo", "private": False, "default_branch": "main", "fork": False,
        "description": "Python project", "language": "Python", "pushed_at": "2026-01-01T00:00:00Z"}
CONTACTS = "Email: person@example.com\nPhone:\n0771234567\nHome address:\n123 Example Street\nDOB: 2000-01-02\n"


class HTTP:
    def __init__(self, data, status=200, raw=None, headers=None):
        self.status_code = status
        self.body = json.dumps(data).encode() if raw is None else raw
        self.headers = headers or {}
        self.closed = False
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.closed = True
    def iter_content(self, chunk_size):
        for index in range(0, len(self.body), chunk_size):
            yield self.body[index:index + chunk_size]


class Network:
    def __init__(self):
        self.responses, self.calls = {}, []
        self.trust_env = True
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def get(self, url, **kwargs):
        assert url.startswith("https://api.github.com/repos/")
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        assert 0 < kwargs["timeout"] <= 5
        assert not self.trust_env and "Authorization" not in kwargs["headers"]
        path = url.removeprefix("https://api.github.com")
        self.calls.append(path)
        value = self.responses.get(path, HTTP({}, 404))
        if isinstance(value, Exception):
            raise value
        return value


def configure(network, repo=REPO, files=None, truncated=False):
    files = files if files is not None else {"README.md": CONTACTS.encode()}
    base = "/repos/" + repo["full_name"]
    network.responses[base + "/git/ref/heads/main"] = HTTP({"object": {"sha": COMMIT, "type": "commit"}})
    network.responses[base + "/git/commits/" + COMMIT] = HTTP({"tree": {"sha": TREE}})
    entries = []
    for index, (path, content) in enumerate(files.items()):
        sha = format(index + 1, "040x")
        entries.append({"path": path, "type": "blob", "mode": "100644", "size": len(content), "sha": sha, "url": "https://evil.invalid/ignored"})
        network.responses[base + "/git/blobs/" + sha] = HTTP({"encoding": "base64", "content": base64.b64encode(content).decode()})
    network.responses[base + "/git/trees/" + TREE] = HTTP({"tree": entries, "truncated": truncated})
    return entries


@pytest.fixture
def network(monkeypatch):
    result = Network()
    configure(result)
    monkeypatch.setattr(scan.requests, "Session", lambda: result)
    return result


def test_supported_patterns_have_masked_line_revision_evidence(network):
    result = scan.scan_public_files([REPO])
    assert {item["kind"] for item in result["evidence"]} == set(privacy.SUPPORTED_KINDS)
    assert next(item for item in result["evidence"] if item["kind"] == "phone")["line_number"] == 3
    assert all(item["revision"] == COMMIT and item["file_path"] == "README.md" for item in result["evidence"])
    assert "person@example.com" not in json.dumps(result) and "0771234567" not in json.dumps(result)
    assert "123 Example Street" not in json.dumps(result) and "2000-01-02" not in json.dumps(result)
    assert result["coverage"]["status"] == "checked" and len(network.calls) == 4


def test_public_forks_are_included(network):
    assert scan.scan_public_files([{**REPO, "fork": True}])["coverage"]["files_checked"] == 1


@pytest.mark.parametrize("repo", [{**REPO, "private": True}, {**REPO, "private": None}, {**REPO, "full_name": "../repo"}, {**REPO, "full_name": "https://evil.invalid"}])
def test_unverified_or_invalid_repository_never_requested(network, repo):
    result = scan.scan_public_files([repo])
    assert not network.calls and result["coverage"]["status"] == "unavailable"


@pytest.mark.parametrize("mode,kind", [("120000", "blob"), ("160000", "commit"), ("040000", "tree")])
def test_symlinks_submodules_and_directories_are_not_fetched(network, mode, kind):
    entries = configure(network)
    entries[0].update(mode=mode, type=kind)
    network.responses["/repos/fixture/repo/git/trees/" + TREE] = HTTP({"tree": entries})
    result = scan.scan_public_files([REPO])
    assert result["coverage"]["files_checked"] == 0
    assert len(network.calls) == 3


def test_missing_readme_is_not_reported_as_clean(network):
    configure(network, files={})
    result = scan.scan_public_files([REPO])
    assert result["coverage"]["status"] == "no_supported_files"
    assert any(file["status"] == "not_found" for file in result["coverage"]["repositories"][0]["files"])


def test_unsupported_paths_and_links_not_followed(network):
    configure(network, files={"src/main.py": CONTACTS.encode(), "../README.md": CONTACTS.encode(), "README.md": b"https://evil.invalid/secret"})
    result = scan.scan_public_files([REPO])
    assert len(network.calls) == 4
    assert result["evidence"] == []
    assert result["coverage"]["files_checked"] == 1


@pytest.mark.parametrize("content", [b"\x00binary", b"\xff\xfeinvalid-utf8"])
def test_binary_and_non_utf8_files_are_skipped(network, content):
    configure(network, files={"README.md": content})
    assert scan.scan_public_files([REPO])["coverage"]["files_checked"] == 0


def test_oversized_file_skipped_before_download(network):
    entries = configure(network)
    entries[0]["size"] = scan.MAX_FILE_BYTES + 1
    network.responses["/repos/fixture/repo/git/trees/" + TREE] = HTTP({"tree": entries})
    assert scan.scan_public_files([REPO])["coverage"]["files_checked"] == 0
    assert len(network.calls) == 3


def test_one_file_failure_does_not_discard_other_findings(network):
    configure(network, files={"README.md": CONTACTS.encode(), "SECURITY.md": CONTACTS.encode()})
    network.responses["/repos/fixture/repo/git/blobs/" + format(1, "040x")] = requests.Timeout()
    result = scan.scan_public_files([REPO])
    assert result["evidence"] and result["coverage"]["status"] == "partial"
    assert result["coverage"]["files_checked"] == 1


@pytest.mark.parametrize("status", [403, 429])
def test_denied_or_rate_limited_stops_requests(network, status):
    network.responses["/repos/fixture/repo/git/ref/heads/main"] = HTTP({}, status)
    result = scan.scan_public_files([REPO] * 5)
    assert len(network.calls) == 1
    assert result["coverage"]["stop_reason"] == "rate_limited_or_denied"


def test_streamed_response_is_bounded_and_closed(network):
    response = HTTP({}, raw=b"x" * (scan.MAX_RESPONSE_BYTES + 1))
    network.responses["/repos/fixture/repo/git/ref/heads/main"] = response
    result = scan.scan_public_files([REPO])
    assert response.closed and result["coverage"]["files_checked"] == 0


def test_content_length_bound_prevents_stream_read(network):
    response = HTTP({}, headers={"Content-Length": str(scan.MAX_RESPONSE_BYTES + 1)})
    response.iter_content = Mock(side_effect=AssertionError("Body must not be consumed"))
    network.responses["/repos/fixture/repo/git/ref/heads/main"] = response
    assert scan.scan_public_files([REPO])["coverage"]["files_checked"] == 0
    response.iter_content.assert_not_called()


def test_limits_repository_count_files_requests_bytes(network, monkeypatch):
    configure(network, files={"README.md": CONTACTS.encode(), "CONTRIBUTING.md": CONTACTS.encode(), "SECURITY.md": CONTACTS.encode(), "README.txt": CONTACTS.encode()})
    result = scan.scan_public_files([REPO] * 6)
    assert result["coverage"]["repositories_selected"] == 5
    assert len(network.calls) == 25
    assert result["coverage"]["stop_reason"] == "request_budget"
    assert all(sum(file["status"] == "checked" for file in repo["files"]) <= 3 for repo in result["coverage"]["repositories"])
    assert result["coverage"]["decoded_bytes"] <= scan.MAX_TOTAL_BYTES
    monkeypatch.setattr(scan, "MAX_TOTAL_BYTES", 1)
    assert scan.scan_public_files([REPO])["coverage"]["stop_reason"] == "decoded_byte_budget"


def test_elapsed_deadline_skips_requests(network):
    assert scan.scan_public_files([REPO], overall_deadline=0)["coverage"]["stop_reason"] == "elapsed_budget"
    assert not network.calls


def test_truncated_tree_and_bad_json_are_explicit(network):
    configure(network, truncated=True)
    assert scan.scan_public_files([REPO])["coverage"]["status"] == "partial"
    network.responses["/repos/fixture/repo/git/ref/heads/main"] = HTTP({}, raw=b"invalid")
    assert scan.scan_public_files([REPO])["coverage"]["repositories"][0]["reason"] == "invalid_response"


def test_existing_source_evidence_retained_when_file_findings_overflow(network):
    configure(network, files={"README.md": "\n".join(f"person{i}@example.com" for i in range(80)).encode()})
    files = scan.scan_public_files([REPO])
    result = privacy.collect_privacy_evidence("", "Phone: 0771234567", repository_file_data=files)
    assert len(result["evidence"]) == 50 and result["omitted_findings_count"] == 31
    assert result["evidence"][0]["source"] == "linkedin"
    assert result["coverage"]["github_repository_files"]["findings_count"] == 80


def test_repository_label_masked_even_with_unprotected_report(network):
    repo = {**REPO, "name": "0771234567", "full_name": "fixture/0771234567"}
    configure(network, repo=repo)
    assert "0771234567" not in json.dumps(scan.scan_public_files([repo]))


def test_disabled_requests_keep_legacy_limits():
    result = privacy.collect_privacy_evidence("", "Python", repository_file_data=scan.empty_result())
    assert result["coverage"]["github_repository_files"]["status"] == "disabled"
    assert privacy.GITHUB_LIMITATIONS[1] in result["limitations"]


@pytest.mark.parametrize("policy", ["mask_contacts", "mask_contacts_and_handle", "none"])
def test_file_scan_never_changes_career_or_ml_and_persists_only_masked_evidence(api, network, monkeypatch, policy):
    client, sessions = api
    captured = []
    monkeypatch.setattr(ml_classifier, "predict_role", lambda text, **kwargs: captured.append(text) or {"model_available": False})
    def metadata(*args, **kwargs):
        return {"username": "fixture", "skills": ["python"], "languages": ["python"], "repo_count": 1,
                "source_state": "analysed", "repository_state": "analysed", "repository_coverage": "complete",
                "privacy_data": privacy.collect_github_privacy_data(profile={"bio": "Python"}, repositories=[REPO], repository_state="analysed"),
                **({"repository_file_privacy": scan.scan_public_files([REPO])} if kwargs.get("scan_repository_files") else {})}
    monkeypatch.setattr(extraction, "extract_from_github", metadata)
    inputs = {**BASE, "github_username": "fixture", "linkedin_text": "Python developer", "report_redaction": policy}
    old = client.post("/api/analyze", data=inputs).json()
    result = client.post("/api/analyze", data={**inputs, "scan_repository_files": "true"}).json()
    assert old["gap_analysis"] == result["gap_analysis"] and captured[0] == captured[1]
    assert result["visibility_assessment"]["coverage"]["github_repository_files"]["status"] == "checked"
    assert any(item.get("source") == "github_repository_file" for item in result["recommendations"])
    assert privacy.GITHUB_LIMITATIONS[1] not in result["visibility_assessment"]["limitations"]
    assert "person@example.com" not in json.dumps(result)
    saved = client.get(f"/api/reports/{result['id']}").json()
    assert "0771234567" not in json.dumps(saved)
    with sessions() as db:
        raw = db.query(database.Report).filter_by(id=result["id"]).one().report_json
        assert "person@example.com" not in raw and CONTACTS not in raw


def test_invalid_text_still_consumes_decoded_budget(network, monkeypatch):
    configure(network, files={"README.md": b"\0binary", "SECURITY.md": CONTACTS.encode()})
    monkeypatch.setattr(scan, "MAX_TOTAL_BYTES", len(CONTACTS.encode()))
    result = scan.scan_public_files([REPO])
    assert result["coverage"]["decoded_bytes"] == len(b"\0binary")
    assert result["coverage"]["stop_reason"] == "decoded_byte_budget"


def test_blob_size_mismatch_cannot_bypass_decode_bound(network):
    entries = configure(network, files={"README.md": b"a"})
    network.responses["/repos/fixture/repo/git/blobs/" + entries[0]["sha"]] = HTTP({"encoding": "base64", "content": base64.b64encode(b"x" * 10000).decode()})
    result = scan.scan_public_files([REPO])
    assert result["coverage"]["decoded_bytes"] == 0
    assert result["coverage"]["files_checked"] == 0


def test_real_extraction_calls_scanner_only_when_enabled(network, monkeypatch):
    def response(data):
        value = requests.Response()
        value.status_code = 200
        value._content = json.dumps(data).encode()
        return value
    get = Mock(side_effect=[response({"bio": "Python", "name": "Fixture", "public_repos": 1}), response([REPO]),
                           response({"bio": "Python", "name": "Fixture", "public_repos": 1}), response([REPO])])
    monkeypatch.setattr(extraction.requests, "get", get)
    old = extraction.extract_from_github("fixture")
    assert not network.calls and "repository_file_privacy" not in old
    new = extraction.extract_from_github("fixture", scan_repository_files=True)
    assert new["repository_file_privacy"]["coverage"]["files_checked"] == 1
    assert old["skills"] == new["skills"] and old["repo_count"] == new["repo_count"]
    assert get.call_count == 4


def test_response_arriving_after_request_deadline_is_not_accepted(network, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(scan.time, "monotonic", lambda: clock[0])
    response = network.responses["/repos/fixture/repo/git/ref/heads/main"]
    original = response.iter_content
    def delayed(chunk_size):
        clock[0] = 6
        yield from original(chunk_size)
    response.iter_content = delayed
    result = scan.scan_public_files([REPO])
    assert result["coverage"]["repositories"][0]["reason"] == "request_timeout"
    assert result["coverage"]["files_checked"] == 0


@pytest.mark.parametrize("data", [{"encoding": "utf-8", "content": "hello"}, {"encoding": "base64", "content": "invalid!"}])
def test_unsupported_blob_payloads_are_skipped(network, data):
    network.responses["/repos/fixture/repo/git/blobs/" + format(1, "040x")] = HTTP(data)
    assert scan.scan_public_files([REPO])["coverage"]["files_checked"] == 0
