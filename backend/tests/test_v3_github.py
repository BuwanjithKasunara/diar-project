import base64
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import config, main
from app.modules import extraction as ex


FIXTURES = Path(__file__).parent / "fixtures"
GITHUB = json.loads((FIXTURES / "github_v3.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, body, status_code=200, *, links=None, text=None):
        self._body = body
        self.status_code = status_code
        self.links = links or {}
        self.text = text

    def json(self):
        return deepcopy(self._body)


class GitHubSession:
    """URL-aware, network-free GitHub session used by extraction tests."""

    def __init__(self, profile, pages, readmes=None, readme_statuses=None):
        self.profile = profile
        self.pages = pages
        self.readmes = readmes or {}
        self.readme_statuses = readme_statuses or {}
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get(self, url, **kwargs):
        params = kwargs.get("params") or {}
        self.calls.append({"url": url, "params": deepcopy(params)})
        if url.endswith("/users/synthetic-ai"):
            return FakeResponse(self.profile)
        if url.endswith("/users/synthetic-ai/repos"):
            page = int(params.get("page", 1))
            body = self.pages.get(page, [])
            links = {"next": {"url": "synthetic"}} if page in self.pages and page + 1 in self.pages else {}
            return FakeResponse(body, links=links)
        if "/repos/synthetic-ai/" in url and url.endswith("/readme"):
            name = url.rsplit("/", 2)[-2]
            status = self.readme_statuses.get(name, 200 if name in self.readmes else 404)
            if status != 200:
                return FakeResponse({}, status_code=status)
            encoded = base64.b64encode(self.readmes[name].encode("utf-8")).decode("ascii")
            return FakeResponse({"encoding": "base64", "content": encoded})
        raise AssertionError(f"Unexpected GitHub URL: {url}")


def install_session(monkeypatch, session):
    monkeypatch.setattr(ex.requests, "Session", lambda: session)
    return session


def scan_snapshot(monkeypatch, *, readme_statuses=None, as_of=None):
    session = install_session(
        monkeypatch,
        GitHubSession(
            deepcopy(GITHUB["profile"]),
            {1: deepcopy(GITHUB["repositories"])},
            deepcopy(GITHUB["readmes"]),
            readme_statuses,
        ),
    )
    result = ex.extract_from_github(
        "synthetic-ai",
        benchmark=main.BENCHMARKS["AI Engineer"],
        as_of=as_of or datetime.fromisoformat(GITHUB["as_of"]),
    )
    return result, session


def test_github_enriches_names_topics_readmes_and_provenance(monkeypatch):
    result, session = scan_snapshot(monkeypatch)

    assert result["source_status"] == {"status": "analysed", "reason": None}
    assert result["repo_count"] == 7  # Public, owned, non-fork repositories; archived repos remain inventory facts.
    assert result["recently_pushed_owned_repo_count"] == 5
    assert result["last_owned_repository_push_at"] == "2025-12-31T00:00:00+00:00"

    readme_calls = [c["url"].rsplit("/", 2)[-2] for c in session.calls if c["url"].endswith("/readme")]
    assert readme_calls == GITHUB["expected_selected_readmes"]
    assert "archived-ml-course" not in readme_calls
    assert "old-popular-unrelated" not in readme_calls

    evidence = result["evidence"]
    assert evidence
    assert len({item["id"] for item in evidence}) == len(evidence)
    assert all(item["id"].startswith("ev-") for item in evidence)
    assert all(item["origin"] and item["artifact_type"] and item["excerpt"] and
               item["extraction_method"] for item in evidence)
    assert all(item["repository_locator"] == item["repository"] for item in evidence)

    readme_evidence = [item for item in evidence if item["origin"] == "repository_readme"]
    assert readme_evidence and {item["strength"] for item in readme_evidence} == {1.0}
    assert {item["artifact_type"] for item in readme_evidence} == {"readme"}
    assert all(item["repository"].startswith("synthetic-ai/") for item in readme_evidence)
    assert any(item["skill"] == "retrieval augmented generation" for item in readme_evidence)

    topic = [item for item in evidence if item["origin"] == "repository_topic"]
    assert topic and {item["strength"] for item in topic} == {0.6}
    assert {item["artifact_type"] for item in topic} == {"topic"}
    descriptions = [item for item in evidence if item["origin"] == "repository_description"]
    assert descriptions and {item["strength"] for item in descriptions} == {0.8}
    assert {item["artifact_type"] for item in descriptions} == {"description"}


def test_github_evidence_ids_are_stable_across_identical_scans(monkeypatch):
    first, _ = scan_snapshot(monkeypatch)
    second, _ = scan_snapshot(monkeypatch)
    assert [item["id"] for item in first["evidence"]] == [item["id"] for item in second["evidence"]]


def test_github_language_whitelist_maps_dockerfile_and_keeps_unknown_metadata(monkeypatch):
    result, _ = scan_snapshot(monkeypatch)

    language_evidence = [item for item in result["evidence"] if item["origin"] == "repository_language"]
    assert any(item["skill"] == "docker" and item["repository"].endswith("/model-api")
               for item in language_evidence)
    assert not {"tex", "brainfuck"} & {item["skill"] for item in language_evidence}
    assert {"dockerfile", "tex", "brainfuck"} <= set(result["languages"])


def test_readme_rate_limit_returns_partial_evidence_without_discarding_inventory(monkeypatch):
    result, _ = scan_snapshot(monkeypatch, readme_statuses={"agentic-rag-langgraph": 403})

    assert result["source_status"]["status"] == "partial"
    assert "README" in result["source_status"]["reason"]
    assert "403" in result["source_status"]["reason"]
    assert result["repo_count"] == 7
    assert result["recently_pushed_owned_repo_count"] == 5
    assert any(item["origin"] == "repository_topic" for item in result["evidence"])


@pytest.mark.parametrize("status_code", [403, 429])
def test_repository_inventory_rate_limit_is_partial_and_recency_unavailable(monkeypatch, status_code):
    class InventoryFailureSession(GitHubSession):
        def get(self, url, **kwargs):
            if url.endswith("/users/synthetic-ai/repos"):
                self.calls.append({"url": url, "params": deepcopy(kwargs.get("params") or {})})
                return FakeResponse({}, status_code=status_code)
            return super().get(url, **kwargs)

    session = install_session(
        monkeypatch,
        InventoryFailureSession(deepcopy(GITHUB["profile"]), {}, deepcopy(GITHUB["readmes"])),
    )
    result = ex.extract_from_github(
        "synthetic-ai",
        benchmark=main.BENCHMARKS["AI Engineer"],
        as_of=datetime.fromisoformat(GITHUB["as_of"]),
    )

    assert result["source_status"]["status"] == "partial"
    assert str(status_code) in result["source_status"]["reason"]
    assert result["repo_count"] is None
    assert result["recently_pushed_owned_repo_count"] is None
    assert result["last_owned_repository_push_at"] is None


def test_github_scan_never_exceeds_eleven_requests(monkeypatch):
    pages = {}
    for page in range(1, 6):
        pages[page] = [
            {
                "name": f"repo-{page}-{index}",
                "full_name": f"synthetic-ai/repo-{page}-{index}",
                "fork": False,
                "archived": False,
                "language": "Python",
                "description": "Python utility",
                "topics": [],
                "stargazers_count": index,
                "pushed_at": f"2025-{page:02d}-01T00:00:00Z",
            }
            for index in range(100)
        ]
    session = install_session(monkeypatch, GitHubSession(deepcopy(GITHUB["profile"]), pages))

    ex.extract_from_github(
        "synthetic-ai",
        benchmark=main.BENCHMARKS["AI Engineer"],
        as_of=datetime.fromisoformat(GITHUB["as_of"]),
    )

    assert len(session.calls) == 11  # profile + five repository pages + five README attempts
    assert sum(c["url"].endswith("/readme") for c in session.calls) == config.MAX_GITHUB_READMES == 5


def test_recency_is_raw_and_deterministic_for_injected_as_of(monkeypatch):
    first, _ = scan_snapshot(monkeypatch, as_of=datetime(2026, 1, 1, tzinfo=timezone.utc))
    repeated, _ = scan_snapshot(monkeypatch, as_of=datetime(2026, 1, 1, tzinfo=timezone.utc))
    later, _ = scan_snapshot(monkeypatch, as_of=datetime(2026, 7, 1, tzinfo=timezone.utc))

    assert first["recently_pushed_owned_repo_count"] == repeated["recently_pushed_owned_repo_count"] == 5
    assert later["recently_pushed_owned_repo_count"] == 0
    assert first["last_owned_repository_push_at"] == later["last_owned_repository_push_at"]
    assert "inactive" not in json.dumps(first).lower()


def test_q_learning_is_a_claim_not_a_plan():
    evidence = ex.extract_evidence(
        "Implemented Q-learning for a reinforcement learning research project.",
        "resume",
    )
    reinforcement = [item for item in evidence if item["skill"] == "reinforcement learning"]
    assert reinforcement and {item["assertion"] for item in reinforcement} == {"claimed"}

