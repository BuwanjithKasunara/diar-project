"""GitHub retrieval failures must not become negative portfolio evidence."""
import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.main import app
from app.modules import alignment_engine, explainable_ai, extraction, identity_construction


PROFILE = {"name": "Example Developer", "bio": "Experienced in Python.", "public_repos": 1, "followers": 3}
BENCHMARK = {
    "required_skills": ["python"], "preferred_skills": [],
    "min_github_repos": 3, "min_github_languages": 2,
}
PORTFOLIO_RULES = {"R4-repo-count", "R5-stale-codebases", "R5-activity", "R6-languages"}


def _response(status=200, data=None, next_page=False):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(data).encode("utf-8")
    if next_page:
        response.headers["Link"] = '<https://api.github.com/users/example/repos?page=2>; rel="next"'
    return response


def _repo(name="example", fork=False, pushed_at=None):
    return {
        "name": name, "fork": fork, "description": "Python project", "language": "Python",
        "pushed_at": pushed_at or datetime.now(timezone.utc).isoformat(),
        "stargazers_count": 0,
    }


def _mock_github(monkeypatch, profile_response=None, repository_response=None):
    get = Mock(side_effect=[
        profile_response if profile_response is not None else _response(data=PROFILE),
        repository_response if repository_response is not None else _response(data=[_repo()]),
    ])
    monkeypatch.setattr(extraction.requests, "get", get)
    return get


def _analyse(github):
    profile = identity_construction.build_digital_identity_profile({}, github, {})
    result = alignment_engine.run_alignment(profile, BENCHMARK, "Example", "Semi-Public")
    return profile, result


def _assert_portfolio_judgements_withheld(result):
    assert result["gap_analysis"]["github_activity_label"] == "insufficient_evidence"
    assert not PORTFOLIO_RULES.intersection(rule["id"] for rule in result["fired_rules"])


@pytest.mark.parametrize("status", [404, 403, 429, 500])
def test_profile_http_failure_does_not_fetch_repositories(monkeypatch, status):
    get = _mock_github(monkeypatch, profile_response=_response(status, {"message": "Unavailable"}))

    github = extraction.extract_from_github("example")

    assert get.call_count == 1
    assert github["source_state"] == "failed"
    assert github["repository_coverage"] == "unavailable"
    _, result = _analyse(github)
    _assert_portfolio_judgements_withheld(result)


@pytest.mark.parametrize("failure", [requests.Timeout(), _response(data=[]), _response(data="invalid")])
def test_unusable_profile_response_returns_failed_state(monkeypatch, failure):
    get = _mock_github(monkeypatch, profile_response=failure)

    github = extraction.extract_from_github("example")

    assert get.call_count == 1
    assert github["source_state"] == "failed"
    assert github["error"]


@pytest.mark.parametrize("status", [403, 429, 500])
def test_repository_http_failure_preserves_profile_without_portfolio_penalties(monkeypatch, status):
    _mock_github(monkeypatch, repository_response=_response(status, {"message": "Unavailable"}))

    github = extraction.extract_from_github("example")

    assert github["source_state"] == "partial"
    assert github["repository_state"] == "failed"
    assert github["repository_coverage"] == "unavailable"
    assert github["bio"] == PROFILE["bio"]
    assert "python" in github["skills"]
    assert str(status) in github["error"]
    profile, result = _analyse(github)
    assert profile["github"]["repository_state"] == "failed"
    _assert_portfolio_judgements_withheld(result)
    assert "retry_github_analysis" in [rule["action"] for rule in result["fired_rules"]]


@pytest.mark.parametrize("failure", [
    requests.Timeout(), _response(data={"message": "not a list"}), _response(data=["not an object"]),
])
def test_repository_transport_or_shape_failure_preserves_profile(monkeypatch, failure):
    _mock_github(monkeypatch, repository_response=failure)

    github = extraction.extract_from_github("example")

    assert github["repository_state"] == "failed"
    assert github["repositories_fetched_count"] == 0
    assert github["bio"] == PROFILE["bio"]
    assert github["error"]
    _, result = _analyse(github)
    _assert_portfolio_judgements_withheld(result)


@pytest.mark.parametrize("endpoint", ["profile", "repositories"])
def test_invalid_json_is_handled_as_unavailable_evidence(monkeypatch, endpoint):
    malformed = requests.Response()
    malformed.status_code = 200
    malformed._content = b"not json"
    if endpoint == "profile":
        _mock_github(monkeypatch, profile_response=malformed)
    else:
        _mock_github(monkeypatch, repository_response=malformed)

    github = extraction.extract_from_github("example")

    assert github["repository_state"] == "failed"
    assert github["source_state"] == ("failed" if endpoint == "profile" else "partial")
    _, result = _analyse(github)
    _assert_portfolio_judgements_withheld(result)


def test_successfully_retrieved_empty_portfolio_can_receive_portfolio_recommendations(monkeypatch):
    _mock_github(monkeypatch, profile_response=_response(data={**PROFILE, "public_repos": 0}),
                 repository_response=_response(data=[]))

    github = extraction.extract_from_github("example")

    assert github["source_state"] == "analysed"
    assert github["repository_state"] == "analysed"
    assert github["repository_coverage"] == "complete"
    assert github["error"] is None
    _, result = _analyse(github)
    assert result["gap_analysis"]["github_activity_label"] == "inactive"
    assert "R4-repo-count" in [rule["id"] for rule in result["fired_rules"]]


def test_complete_portfolio_retains_activity_analysis_and_excludes_forks(monkeypatch):
    _mock_github(monkeypatch, profile_response=_response(data={**PROFILE, "public_repos": 2}),
                 repository_response=_response(data=[_repo(), _repo("fork", fork=True)]))

    github = extraction.extract_from_github("example")

    assert github["repositories_fetched_count"] == 2
    assert github["repo_count"] == 1
    assert github["repository_coverage"] == "complete"
    _, result = _analyse(github)
    assert result["gap_analysis"]["github_activity_label"] == "active"
    assert "R4-repo-count" in [rule["id"] for rule in result["fired_rules"]]


@pytest.mark.parametrize("next_page, public_count", [(True, 100), (False, 101)])
def test_incomplete_page_withholds_portfolio_judgements_and_discloses_limit(monkeypatch, next_page, public_count):
    repos = [_repo(str(i), pushed_at="2020-01-01T00:00:00Z") for i in range(100)]
    _mock_github(monkeypatch, profile_response=_response(data={**PROFILE, "public_repos": public_count}),
                 repository_response=_response(data=repos, next_page=next_page))

    github = extraction.extract_from_github("example")

    assert github["source_state"] == "partial"
    assert github["repository_state"] == "partial"
    assert github["repository_coverage"] == "limited"
    assert github["repositories_fetched_count"] == 100
    assert "first 100" in github["error"]
    assert "python" in github["skills"]
    profile, result = _analyse(github)
    _assert_portfolio_judgements_withheld(result)
    explanation = explainable_ai.build_explanation_summary(
        profile, "Example", result["gap_analysis"], result["visibility_assessment"], []
    )
    assert "only part of the public portfolio" in explanation["narrative"]


def test_exactly_one_full_page_without_more_repositories_is_complete(monkeypatch):
    _mock_github(monkeypatch, profile_response=_response(data={**PROFILE, "public_repos": 100}),
                 repository_response=_response(data=[_repo(str(i)) for i in range(100)]))

    github = extraction.extract_from_github("example")

    assert github["repository_coverage"] == "complete"
    assert github["error"] is None


@pytest.fixture
def api_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reports.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def test_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[database.get_db] = test_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(database.get_db, None)
        engine.dispose()


@pytest.mark.parametrize("limited", [False, True])
def test_api_persists_warning_and_repository_coverage(api_client, monkeypatch, limited):
    _mock_github(
        monkeypatch,
        repository_response=_response(data=[_repo()], next_page=True) if limited else _response(403),
    )

    response = api_client.post("/api/analyze", data={
        "benchmark_identity": "AI Engineer", "visibility_level": "Semi-Public", "github_username": "example",
    })

    assert response.status_code == 200
    report = response.json()
    assert report["github_warning"]
    assert report["digital_identity_profile"]["github"]["repository_coverage"] == ("limited" if limited else "unavailable")
    assert report["gap_analysis"]["github_activity_label"] == "insufficient_evidence"
    assert not PORTFOLIO_RULES.intersection(item["rule_id"] for item in report["recommendations"])
    saved = api_client.get(f"/api/reports/{report['id']}")
    assert saved.status_code == 200
    assert saved.json()["github_warning"] == report["github_warning"]
    assert saved.json()["digital_identity_profile"]["github"] == report["digital_identity_profile"]["github"]
