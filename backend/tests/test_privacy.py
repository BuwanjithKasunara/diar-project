"""Report redaction, persistence and deletion regression coverage."""
import copy
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.main import app
from app.modules import extraction, ml_classifier, privacy, privacy_assessment


CONTACT = "person@example.com +94 (77) 123-4567"


@pytest.mark.parametrize("mode", ["Semi-Public", "Privacy Focused"])
def test_redaction_covers_every_report_section_without_changing_metrics(mode):
    original = {
        "digital_identity_profile": {"github": {"username": "python", "bio": CONTACT},
                                     "education": [CONTACT], "skills": ["python"]},
        "github_warning": f"Account 'python': {CONTACT}",
        "recommendations": [{"reason": CONTACT}],
        "explanation_summary": {"narrative": CONTACT},
        "ml_prediction": {"top_features": [CONTACT], "confidence": 0.75},
        "repositories": [{"description": CONTACT}],
        "date": "2020-01-01", "years": "2020-2024", "missing": None,
    }
    before = copy.deepcopy(original)
    result = privacy.sanitize_report_for_visibility(original, mode)
    serialized = json.dumps(result)
    assert "person@example.com" not in serialized
    assert "123-4567" not in serialized
    assert result["ml_prediction"]["confidence"] == 0.75
    assert result["date"] == "2020-01-01"
    assert result["years"] == "2020-2024"
    assert result["missing"] is None
    assert result["digital_identity_profile"]["skills"] == ["python"]
    assert original == before
    expected = privacy.ANONYMOUS_USER if mode == "Privacy Focused" else "python"
    assert result["digital_identity_profile"]["github"]["username"] == expected


def test_focus_masks_known_account_references_but_preserves_unrelated_accounts():
    data = {"text": "@python 'python' https://github.com/python/repo github.com/python "
                    "@python-other https://github.com/python-other/repo Python developer"}
    result = privacy.sanitize_report_for_visibility(data, "Privacy Focused", "python")
    assert "@python " not in result["text"]
    assert "'python'" not in result["text"]
    assert "github.com/python " not in result["text"]
    assert "github.com/python/repo" not in result["text"]
    assert "@python-other" in result["text"]
    assert "github.com/python-other/repo" in result["text"]
    assert "Python developer" in result["text"]
    assert privacy.sanitize_report_for_visibility(data, "Semi-Public", "python") == data


def test_public_returns_an_independent_unredacted_copy():
    original = {"nested": [CONTACT]}
    result = privacy.sanitize_report_for_visibility(original, "Fully Public")
    assert result == original
    result["nested"].append("changed")
    assert original == {"nested": [CONTACT]}


@pytest.mark.parametrize("phone", ["+1 555 0199", "0771234567", "+94 (77) 123-4567"])
def test_common_phone_formats(phone):
    assert privacy.mask_contact_details(phone) == "[REDACTED_PHONE]"
    assert privacy.contains_contact_details(phone)


def test_optional_username_and_dates():
    assert privacy.sanitize_github_username(None, "Privacy Focused") is None
    assert privacy.sanitize_github_username("  ", "Privacy Focused") is None
    assert not privacy.contains_contact_details("2020-01-01; 2020–2024")


@pytest.fixture
def saved_reports(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'privacy.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def test_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[database.get_db] = test_db
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.pop(database.get_db, None)
        engine.dispose()


@pytest.mark.parametrize("mode", ["Fully Public", "Semi-Public", "Privacy Focused"])
@pytest.mark.parametrize("policy", privacy.REPORT_POLICIES)
def test_new_report_response_storage_and_history_follow_same_policy(saved_reports, monkeypatch, mode, policy):
    client, sessions = saved_reports
    monkeypatch.setattr(extraction, "extract_from_github", lambda username: {
        "username": username, "bio": CONTACT, "skills": [], "languages": [],
        "repo_count": 0, "profile_complete": False, "source_state": "partial",
        "repository_state": "failed", "error": f"Account '{username}' unavailable: {CONTACT}",
        "privacy_data": privacy_assessment.collect_github_privacy_data(profile={"bio": CONTACT}, repository_state="failed"),
    })
    monkeypatch.setattr(ml_classifier, "predict_role", lambda *args, **kwargs: None)
    response = client.post("/api/analyze", data={
        "benchmark_identity": "AI Engineer", "visibility_level": mode,
        "github_username": "privacy-demo", "linkedin_text": f"Python developer\nEducation: {CONTACT}",
        "report_redaction": policy,
    })
    assert response.status_code == 200
    payload = response.json()
    expected_username = privacy.ANONYMOUS_USER if policy == "mask_contacts_and_handle" else "privacy-demo"
    assert payload["digital_identity_profile"]["public_contact_info_detected"] is True
    with sessions() as session:
        row = session.get(database.Report, payload["id"])
        stored = json.loads(row.report_json)
        assert stored == {key: value for key, value in payload.items() if key != "id"}
        assert row.github_username == expected_username
        assert ("person@example.com" in row.report_json) == (policy == "none")
    history = client.get("/api/reports").json()
    assert history[0]["github_username"] == expected_username
    loaded = client.get(f"/api/reports/{payload['id']}").json()
    assert {key: value for key, value in loaded.items() if key not in ("id", "created_at")} == stored
    if policy == "mask_contacts_and_handle":
        assert "privacy-demo" not in json.dumps(loaded)


def test_legacy_reads_redact_without_silently_rewriting_original_row(saved_reports):
    client, sessions = saved_reports
    original = {"github_warning": f"@legacy-user {CONTACT}",
                "digital_identity_profile": {"github": {"username": "legacy-user"}}}
    with sessions() as session:
        row = database.Report(benchmark_identity="AI Engineer", visibility_level="Privacy Focused",
                              github_username="legacy-user", report_json=json.dumps(original))
        session.add(row)
        session.commit()
        report_id = row.id
    response = client.get(f"/api/reports/{report_id}")
    assert response.status_code == 200
    assert "legacy-user" not in response.text
    assert "person@example.com" not in response.text
    assert client.get("/api/reports").json()[0]["github_username"] == privacy.ANONYMOUS_USER
    with sessions() as session:
        assert json.loads(session.get(database.Report, report_id).report_json) == original


def test_delete_removes_only_selected_report_and_returns_not_found_afterward(saved_reports):
    client, sessions = saved_reports
    with sessions() as session:
        rows = [database.Report(benchmark_identity="AI Engineer", visibility_level="Fully Public",
                                report_json=json.dumps({"marker": marker})) for marker in ("first", "second")]
        session.add_all(rows)
        session.commit()
        first, second = [row.id for row in rows]
    response = client.delete(f"/api/reports/{first}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/reports/{first}").status_code == 404
    assert client.delete(f"/api/reports/{first}").status_code == 404
    assert client.get(f"/api/reports/{second}").json()["marker"] == "second"
    assert [row["id"] for row in client.get("/api/reports").json()] == [second]
    with sessions() as session:
        assert session.get(database.Report, first) is None


def test_default_and_invalid_policy_do_not_depend_on_visibility(saved_reports, monkeypatch):
    client, sessions = saved_reports
    monkeypatch.setattr(ml_classifier, "predict_role", lambda *args, **kwargs: None)
    response = client.post("/api/analyze", data={"benchmark_identity": "AI Engineer",
        "visibility_level": "Fully Public", "linkedin_text": CONTACT})
    assert response.status_code == 200
    assert response.json()["report_metadata"]["report_redaction"] == "mask_contacts"
    assert "person@example.com" not in response.text
    response = client.post("/api/analyze", data={"benchmark_identity": "AI Engineer",
        "visibility_level": "Privacy Focused", "report_redaction": "invalid"})
    assert response.status_code == 400
    with sessions() as session:
        assert session.query(database.Report).count() == 1


def test_report_protection_does_not_change_analysis_and_resume_provenance(saved_reports, monkeypatch):
    client, _ = saved_reports
    inputs = []
    monkeypatch.setattr(extraction, "extract_text_from_pdf", lambda data: "Python engineer Email: person@example.com")
    def predict(text, **kwargs):
        inputs.append(text)
        return {"model_available": False, "confidence": 0.5}
    monkeypatch.setattr(ml_classifier, "predict_role", predict)
    results = []
    for mode in ("Fully Public", "Semi-Public", "Privacy Focused"):
        for policy in privacy.REPORT_POLICIES:
            response = client.post("/api/analyze", data={"benchmark_identity": "AI Engineer",
                "visibility_level": mode, "report_redaction": policy},
                files={"resume": ("synthetic.pdf", b"fixture", "application/pdf")})
            assert response.status_code == 200
            result = response.json()
            assert result["visibility_assessment"]["coverage"]["resume"]["status"] == "application_document"
            assert not any(item.get("source") == "resume" for item in result["recommendations"])
            results.append(result)
    assert all(item["gap_analysis"] == results[0]["gap_analysis"] for item in results)
    assert all(item["ml_prediction"] == results[0]["ml_prediction"] for item in results)
    assert len(set(inputs)) == 1
    for index in (0, 3, 6):
        assert results[index]["recommendations"] == results[index+1]["recommendations"] == results[index+2]["recommendations"]
    public = client.post("/api/analyze", data={"benchmark_identity": "AI Engineer",
        "visibility_level": "Privacy Focused", "resume_publicly_shared": "true"},
        files={"resume": ("synthetic.pdf", b"fixture", "application/pdf")}).json()
    assert public["visibility_assessment"]["coverage"]["resume"]["status"] == "user_declared_public"
    assert any(item.get("source") == "resume" for item in public["recommendations"])


@pytest.mark.parametrize("mode,policy", list(privacy.LEGACY_POLICIES.items()))
def test_legacy_policy_is_only_a_read_fallback(saved_reports, mode, policy):
    client, sessions = saved_reports
    original = {"visibility_assessment": {"findings": ["Old finding"]}, "text": CONTACT}
    with sessions() as session:
        row = database.Report(benchmark_identity="AI Engineer", visibility_level=mode,
                              github_username="legacy", report_json=json.dumps(original))
        session.add(row); session.commit(); report_id = row.id
    payload = client.get(f"/api/reports/{report_id}").json()
    assert payload["report_metadata"]["report_redaction"] == policy
    assert payload["visibility_assessment"] == original["visibility_assessment"]
    with sessions() as session:
        assert json.loads(session.get(database.Report, report_id).report_json) == original
