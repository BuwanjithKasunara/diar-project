"""Source-aware masked evidence foundation; no live network or user data."""
import copy
import json
import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.main import app
from app.modules import extraction, privacy_assessment as privacy


def _scan(text, location="bio", status="observed_public"):
    return privacy.scan_text_for_exposure(text, "github_profile", location, status, "fixture")


@pytest.mark.parametrize("text,kind,basis", [
    ("Email: person@example.com", "email", "pattern"),
    ("Phone: +94 (77) 123-4567", "phone", "labelled"),
    ("Mobile: 0771234567", "phone", "labelled"),
    ("Tel: +1 555-0199", "phone", "labelled"),
    ("Contact +94 77 123 4567", "phone", "possible"),
    ("Address: 123 Example Street", "street_address", "labelled"),
    ("Home address: 12A Sample Road", "street_address", "labelled"),
    ("DOB: 1990-05-12", "date_of_birth", "labelled"),
    ("Date of birth: 12/05/1990", "date_of_birth", "labelled"),
])
def test_supported_patterns_are_masked_and_explain_their_detection_basis(text, kind, basis):
    findings = _scan(text)
    assert len(findings) == 1
    item = findings[0]
    assert item["kind"] == kind
    assert item["detection_basis"] == basis
    assert item["exposure_status"] == "observed_public"
    assert item["recommendation_eligible"] is True
    assert item["display_evidence"] != text
    assert len(item["display_evidence"]) <= privacy.MAX_EXCERPT_LENGTH
    assert "example.com" not in item["display_evidence"]


@pytest.mark.parametrize("text", [
    "Worked from 2020-2024", "Started 2020-01-01", "Updated 12/05/2020",
    "Version: 1.2.3.4.5.6.7", "Version: 123456789", "Build: 123456789",
    "Ticket: 123456789", "Order: 123456789", "ID: 123456789",
    "Stars: 1234567", "1234567 followers", "1234567 views", "1234567 users",
    "Salary: 123456789", "10 years experience", "Colombo, Sri Lanka",
    "Address: Colombo", "Date: 1990-05-12", "DOB: 1990-99-99",
    "Date of birth: 01/01/2999", "Python developer at Example Company",
])
def test_career_metrics_dates_versions_and_unsupported_context_are_not_exposure(text):
    assert _scan(text) == []


def test_structured_location_can_identify_street_but_not_city():
    assert _scan("Colombo, Sri Lanka", location="location") == []
    finding = _scan("123 Example Street", location="location")[0]
    assert finding["kind"] == "street_address"
    assert finding["detection_basis"] == "structured_field"
    assert finding["display_evidence"] == "[ADDRESS]"
    labelled = _scan("Address: 123 Example Street", location="location")
    assert len(labelled) == 1
    assert labelled[0]["detection_basis"] == "labelled"


@pytest.mark.parametrize("value", [None, "", "  ", 123, {}])
def test_missing_and_nontext_fields_do_not_create_evidence(value):
    assert _scan(value) == []


def test_unknown_status_is_rejected_without_echoing_source_text():
    with pytest.raises(ValueError, match="Unknown exposure status") as error:
        _scan("person@example.com", status="unexpected")
    assert "example.com" not in str(error.value)


def test_full_masking_before_cropping_handles_neighboring_and_overlapping_details():
    text = "x" * 180 + " Email: person@example.com; phone: +94 77 123 4567\nAddress: 123 Example Street phone 0771234567"
    findings = _scan(text)
    assert {item["kind"] for item in findings} == {"email", "phone", "street_address"}
    for item in findings:
        assert len(item["display_evidence"]) <= 160
        assert "person@example.com" not in item["display_evidence"]
        assert "123 4567" not in item["display_evidence"]
        assert "0771234567" not in item["display_evidence"]
        assert "123 Example Street" not in item["display_evidence"]


def test_duplicates_are_transient_and_per_field_not_per_platform():
    profile = {"bio": "person@example.com person@example.com", "email": "person@example.com"}
    result = privacy.collect_github_privacy_data(profile=profile, repositories=[], repository_state="analysed", repository_coverage="complete")
    assert result["findings_count"] == 2
    assert {item["location"] for item in result["evidence"]} == {"bio", "email"}
    assert "person@example.com" not in json.dumps(result)
    assert all(set(item) == {"id", "source", "location", "kind", "exposure_status", "detection_basis", "display_evidence", "recommendation_eligible"} for item in result["evidence"])
    assert profile["email"] == "person@example.com"


def test_findings_cap_discloses_omissions_but_still_checks_later_repositories():
    repos = [{"name": f"repo-{index}", "description": f"Email: candidate{index}@example.com"} for index in range(100)]
    result = privacy.collect_github_privacy_data(profile={}, repositories=repos, repository_state="partial", repository_coverage="limited")
    assert len(result["evidence"]) == 50
    assert result["findings_count"] == 100
    assert result["omitted_findings_count"] == 50
    assert result["coverage"]["github_repositories"]["repositories_checked"] == 100
    assert result["coverage"]["github_repositories"]["status"] == "limited"
    assert "candidate" not in json.dumps(result)


def test_aggregate_provenance_and_limits_preserve_input_data():
    github = privacy.collect_github_privacy_data(profile={"email": "person@example.com"})
    before = copy.deepcopy(github)
    result = privacy.collect_privacy_evidence("Email: applicant@example.com", "Headline\n" + "x" * 200 + "\nPhone: 0771234567", github)
    findings = {item["source"]: item for item in result["evidence"]}
    assert findings["resume"]["exposure_status"] == "application_document"
    assert findings["resume"]["recommendation_eligible"] is False
    assert findings["linkedin"]["exposure_status"] == "supplied_text_unknown_audience"
    assert findings["linkedin"]["recommendation_eligible"] is True
    assert result["coverage"]["linkedin"]["audience_verified"] is False
    assert findings["github_profile"]["exposure_status"] == "observed_public"
    assert "@example.com" not in json.dumps(result)
    result["evidence"][-1]["kind"] = "changed"
    assert github == before
    declared = privacy.collect_privacy_evidence("Phone: 0771234567", "", resume_publicly_shared=True)
    assert declared["evidence"][0]["exposure_status"] == "user_declared_public"
    assert declared["evidence"][0]["recommendation_eligible"] is True


def test_empty_sources_have_missing_coverage_not_a_clean_bill_of_health():
    result = privacy.collect_privacy_evidence("", "")
    assert result["evidence"] == []
    assert result["coverage"]["resume"]["status"] == "not_supplied"
    assert result["coverage"]["linkedin"]["status"] == "not_supplied"
    assert result["coverage"]["github_profile"]["status"] == "not_supplied"
    assert result["coverage"]["github_repositories"]["status"] == "not_supplied"
    assert result["limitations"]


def _response(status=200, data=None, limited=False):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(data).encode()
    if limited:
        response.headers["Link"] = '<https://api.github.com/users/fixture/repos?page=2>; rel="next"'
    return response


def _mock_github(monkeypatch, profile=None, repos=None, repo_status=200, limited=False):
    get = Mock(side_effect=[_response(data=profile if profile is not None else {"name": "Fixture", "bio": "Python developer", "public_repos": len(repos or [])}),
                            _response(repo_status, data=repos if repos is not None else [], limited=limited)])
    monkeypatch.setattr(extraction.requests, "get", get)
    return get


def test_repository_beyond_top_five_and_fork_are_scanned_with_no_extra_requests(monkeypatch):
    repos = [{"name": f"repo-{index}", "description": "Python project", "language": "Python", "stargazers_count": 100 - index, "fork": index == 99} for index in range(100)]
    repos[5]["description"] = "Phone: 0771234567"
    repos[99]["description"] = "person@example.com"
    repos[99]["topics"] = ["other@example.com"]
    get = _mock_github(monkeypatch, repos=repos)
    github = extraction.extract_from_github("fixture")
    assert get.call_count == 2
    assert github["repo_count"] == 99
    assert len(github["top_repos"]) == 5
    evidence = github["privacy_data"]["evidence"]
    assert {item["repository_name"] for item in evidence} == {"repo-5", "repo-99"}
    assert {item["location"] for item in evidence} == {"description", "topics[0]"}
    assert "person@example.com" not in json.dumps(github["privacy_data"])
    assert "other@example.com" not in json.dumps(github["privacy_data"])


def test_repository_name_contact_is_masked_in_evidence_metadata(monkeypatch):
    _mock_github(monkeypatch, repos=[{"name": "0771234567", "description": "Email: person@example.com"}])
    result = extraction.extract_from_github("fixture")["privacy_data"]
    assert "0771234567" not in json.dumps(result)
    assert all(item["repository_name"] == "[PHONE]" for item in result["evidence"])


@pytest.mark.parametrize("failure", [403, requests.Timeout("fixture"), "invalid_json"])
def test_repository_failures_preserve_public_profile_evidence(monkeypatch, failure):
    second = failure if isinstance(failure, Exception) else _response(failure if isinstance(failure, int) else 200)
    if failure == "invalid_json":
        second._content = b"invalid"
    get = Mock(side_effect=[_response(data={"bio": "person@example.com", "public_repos": 1}), second])
    monkeypatch.setattr(extraction.requests, "get", get)
    result = extraction.extract_from_github("fixture")["privacy_data"]
    assert result["evidence"][0]["source"] == "github_profile"
    assert result["coverage"]["github_profile"]["status"] == "checked"
    assert result["coverage"]["github_profile"]["checked_fields"] == ["bio"]
    assert result["coverage"]["github_repositories"]["status"] == "failed"


@pytest.mark.parametrize("limited", [False, True])
def test_successful_metadata_and_limited_coverage_are_explicit(monkeypatch, limited):
    _mock_github(monkeypatch, repos=[{"name": "demo", "description": "person@example.com"}], limited=limited)
    result = extraction.extract_from_github("fixture")["privacy_data"]
    coverage = result["coverage"]["github_repositories"]
    assert coverage["status"] == ("limited" if limited else "checked")
    assert coverage["repositories_checked"] == 1
    assert coverage["files_inspected"] is False
    assert len(result["evidence"]) == 1


def test_empty_success_and_profile_failure_are_distinct(monkeypatch):
    _mock_github(monkeypatch)
    empty = extraction.extract_from_github("fixture")["privacy_data"]
    assert empty["coverage"]["github_repositories"]["status"] == "checked"
    assert empty["coverage"]["github_repositories"]["repositories_checked"] == 0
    get = Mock(return_value=_response(404))
    monkeypatch.setattr(extraction.requests, "get", get)
    failed = extraction.extract_from_github("fixture")["privacy_data"]
    assert failed["coverage"]["github_profile"]["status"] == "failed"
    assert failed["coverage"]["github_repositories"]["status"] == "failed"
    assert failed["evidence"] == []
    assert get.call_count == 1


def test_evidence_collection_does_not_change_career_extraction(monkeypatch):
    profile = {"name": "Fixture", "bio": "Experienced Python developer. person@example.com", "public_repos": 1}
    repos = [{"name": "demo", "description": "Python project Phone: 0771234567", "language": "Python", "fork": False}]
    get = _mock_github(monkeypatch, profile=profile, repos=repos)
    with_evidence = extraction.extract_from_github("fixture")
    assert get.call_count == 2
    monkeypatch.setattr(privacy, "collect_github_privacy_data", lambda **kwargs: {})
    _mock_github(monkeypatch, profile=profile, repos=repos)
    without_evidence = extraction.extract_from_github("fixture")
    assert {key: value for key, value in with_evidence.items() if key != "privacy_data"} == {key: value for key, value in without_evidence.items() if key != "privacy_data"}


def test_foundation_is_not_exposed_or_persisted_by_analysis_api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'reports.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def test_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[database.get_db] = test_db
    _mock_github(monkeypatch, profile={"name": "Fixture", "bio": "Python developer person@example.com", "public_repos": 0})
    try:
        with TestClient(app) as client:
            response = client.post("/api/analyze", data={"benchmark_identity": "AI Engineer", "visibility_level": "Fully Public", "github_username": "fixture"})
            assert response.status_code == 200
            assert "privacy_data" not in response.text
            assert "privacy_evidence" not in response.text
            assert "assessment_version" not in response.text
            with sessions() as session:
                row = session.get(database.Report, response.json()["id"])
                assert "privacy_data" not in row.report_json
                assert "privacy_evidence" not in row.report_json
    finally:
        app.dependency_overrides.pop(database.get_db, None)
        engine.dispose()
