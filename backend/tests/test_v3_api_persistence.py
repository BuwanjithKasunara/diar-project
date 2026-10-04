import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, main
from app.schemas import AnalyzeResponseV2, AnalyzeResponseV3


@pytest.fixture
def isolated_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override():
        with session_factory() as db:
            yield db

    monkeypatch.setattr(database, "init_db", lambda: None)
    main.app.dependency_overrides[database.get_db] = override
    with TestClient(main.app, raise_server_exceptions=True) as client:
        yield client, session_factory
    main.app.dependency_overrides.clear()
    engine.dispose()


def analysis_fields():
    return {
        "benchmark_identity": "AI Engineer",
        "visibility_level": "Privacy Focused",
        "linkedin_text": "Skills: Python, machine learning, PyTorch. Projects: Built an LLM evaluation experiment.",
    }


def legacy_v2_payload():
    payload = {
        "schema_version": 2,
        "benchmark_version": "2",
        "planner_version": "1",
        "benchmark_identity": "AI Engineer",
        "visibility_level": "Semi-Public",
        "github_username": None,
        "digital_identity_profile": {"skills": ["python"]},
        "benchmark_comparison": {"matched_skills": ["python"]},
        "gap_analysis": {
            "matched_skills": ["python"],
            "missing_required_skills": ["machine learning"],
            "missing_preferred_skills": [],
            "skill_match_score": 0.1,
            "skill_match_label": "low",
            "github_activity_score": None,
            "github_activity_label": "insufficient evidence",
            "profile_completeness_score": 0.333,
            "profile_completeness_label": "partial",
            "memberships": {
                "skill_match": {"low": 1.0},
                "github_activity": {},
                "source_coverage": {"partial": 1.0},
            },
            "project_keyword_matches": [],
            "relevant_certifications": [],
        },
        "visibility_assessment": {"selected_level": "Semi-Public", "findings": []},
        "recommendations": [],
        "explanation_summary": {"historical": True},
        "github_warning": None,
        "source_statuses": {
            "resume": {"status": "not_supplied", "reason": None},
            "github": {"status": "not_supplied", "reason": None},
            "linkedin": {"status": "analysed", "reason": None},
        },
        "evidence": [],
        "suggested_plan": {
            "status": "no_actions_needed",
            "steps": [],
            "total_cost": 0,
            "objectives": [],
            "unresolved_objectives": [],
            "expanded_states": 0,
            "optimal": True,
            "fallback_recommendations": [],
        },
        "clarification_requests": [],
    }
    AnalyzeResponseV2.model_validate(payload)
    return payload


def test_analyze_returns_only_v3_neutral_assessment(isolated_client):
    client, _ = isolated_client
    response = client.post("/api/analyze", data=analysis_fields())

    assert response.status_code == 200
    report = response.json()
    AnalyzeResponseV3.model_validate(report)
    assert report["schema_version"] == 3
    assert report["benchmark_version"] == "3"
    assert set(report["assessment"]) == {
        "benchmark_evidence", "source_scope", "github_portfolio_recency"
    }
    assert "gap_analysis" not in report
    serialized = json.dumps(report).lower()
    assert "skill_match_label" not in serialized
    assert "github_activity_label" not in serialized
    assert '"inactive"' not in serialized


def test_v3_report_round_trips_and_history_records_schema_version(isolated_client):
    client, _ = isolated_client
    report = client.post("/api/analyze", data=analysis_fields()).json()

    saved_response = client.post("/api/reports", json=report)
    assert saved_response.status_code == 201
    saved = saved_response.json()
    report_id = saved["id"]
    assert saved["schema_version"] == 3
    assert saved["assessment"] == report["assessment"]

    retrieved = client.get(f"/api/reports/{report_id}").json()
    assert {key: value for key, value in retrieved.items() if key not in {"id", "created_at"}} == report
    history = client.get("/api/reports").json()
    assert history[0]["id"] == report_id
    assert history[0]["schema_version"] == 3


def test_save_temporarily_accepts_v2_without_recalculation(isolated_client):
    client, session_factory = isolated_client
    legacy = legacy_v2_payload()

    response = client.post("/api/reports", json=legacy)
    assert response.status_code == 201
    saved = response.json()
    assert saved["schema_version"] == 2
    assert saved["gap_analysis"] == legacy["gap_analysis"]
    assert "assessment" not in saved

    report_id = saved["id"]
    with session_factory() as db:
        row = db.get(database.Report, report_id)
        assert json.loads(row.report_json) == legacy

    retrieved = client.get(f"/api/reports/{report_id}").json()
    assert {key: value for key, value in retrieved.items() if key not in {"id", "created_at"}} == legacy
    assert client.get("/api/reports").json()[0]["schema_version"] == 2


def test_unversioned_saved_json_is_returned_semantically_unchanged(isolated_client):
    client, session_factory = isolated_client
    legacy_json = '{  "gap_analysis": {"skill_match_score": 0.5}, "custom_legacy_field": [3, 2, 1] }'
    with session_factory() as db:
        row = database.Report(
            benchmark_identity="AI Engineer",
            visibility_level="Semi-Public",
            github_username=None,
            report_json=legacy_json,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        report_id = row.id

    retrieved = client.get(f"/api/reports/{report_id}").json()
    assert {key: value for key, value in retrieved.items() if key not in {"id", "created_at"}} == json.loads(legacy_json)
    assert "assessment" not in retrieved

    with session_factory() as db:
        assert db.get(database.Report, report_id).report_json == legacy_json
    history = client.get("/api/reports").json()
    assert history[0]["schema_version"] is None

