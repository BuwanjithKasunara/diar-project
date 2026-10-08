"""Input limits, conservative evidence and clause-bound skill extraction."""
import pytest
import fitz
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import database
from app.main import app, MAX_RESUME_BYTES
from app.modules import extraction, identity_construction, alignment_engine, ml_classifier


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'foundation.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def get_db():
        with sessions() as session:
            yield session
    app.dependency_overrides[database.get_db] = get_db
    monkeypatch.setattr(ml_classifier, "predict_role", lambda *args, **kwargs: {"model_available": False})
    with TestClient(app) as test_client:
        yield test_client, sessions
    app.dependency_overrides.pop(database.get_db, None)
    engine.dispose()


BASE = {"benchmark_identity": "AI Engineer", "visibility_level": "Privacy Focused"}


@pytest.mark.parametrize("data,status", [
    ({}, 400), ({"linkedin_text": " \n "}, 400),
    ({"github_username": "https://github.com/example"}, 400),
    ({"github_username": "-example"}, 400),
    ({"linkedin_text": "x" * 100001}, 413),
], ids=["empty", "whitespace", "profile-url", "invalid-user", "long-text"])
def test_invalid_inputs_do_not_persist(client, data, status):
    api, sessions = client
    assert api.post("/api/analyze", data={**BASE, **data}).status_code == status
    with sessions() as db:
        assert db.query(database.Report).count() == 0


def pdf_bytes(pages=1, text="", encrypted=False):
    with fitz.open() as doc:
        for _ in range(pages):
            page = doc.new_page()
            if text:
                page.insert_text((72, 72), text)
        return doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="test") if encrypted else doc.tobytes()


@pytest.mark.parametrize("content,status", [
    (b"not a pdf", 400), (b"x" * (MAX_RESUME_BYTES + 1), 413),
    (pdf_bytes(), 400), (pdf_bytes(31, "Python"), 400),
    (pdf_bytes(text="Python", encrypted=True), 400),
], ids=["malformed", "oversized", "image-only", "too-many-pages", "encrypted"])
def test_invalid_pdf_does_not_persist(client, content, status):
    api, sessions = client
    response = api.post("/api/analyze", data=BASE, files={"resume": ("resume.pdf", content, "application/pdf")})
    assert response.status_code == status
    with sessions() as db:
        assert db.query(database.Report).count() == 0


def test_valid_pdf_still_produces_report(client):
    api, _ = client
    response = api.post("/api/analyze", data=BASE, files={"resume": ("resume.pdf", pdf_bytes(text="Python developer with 3 years of experience"), "application/pdf")})
    assert response.status_code == 200
    assert response.json()["digital_identity_profile"]["experience_evidence"]["years"] == 3


def test_failed_github_only_does_not_save_empty_report(client, monkeypatch):
    api, _ = client
    monkeypatch.setattr(extraction, "extract_from_github", lambda username: extraction._github_failure(username, "failed", "Synthetic failure"))
    assert api.post("/api/analyze", data={**BASE, "github_username": "example"}).status_code == 422
    assert api.post("/api/analyze", data={**BASE, "github_username": "example", "linkedin_text": "Python developer"}).status_code == 200


@pytest.mark.parametrize("text,category", [
    ("No experience with Java\nPython developer", "negated"),
    ("Plan to learn Java\nPython developer", "planned"),
    ("Basic Java\nPython developer", "uncertain"),
])
def test_context_stays_on_its_line(text, category):
    result = extraction.extract_contextual_skills(text)
    assert "java" in result[category]
    assert "python" in result["claimed"]


def test_aliases_count_one_mention(monkeypatch):
    monkeypatch.setattr(extraction, "ALL_ALIAS_PATTERNS", ["machine learning", "learning"])
    monkeypatch.setattr(extraction, "ALIAS_TO_CANONICAL", {"machine learning": "machine learning", "learning": "machine learning"})
    assert extraction.extract_contextual_skills("machine learning", fuzzy=False)["frequency"]["machine learning"] == 1


def test_learning_verb_is_not_a_scikit_learn_typo():
    result = extraction.extract_contextual_skills("Plan to learn Docker.")
    assert result["planned"] == ["docker"]
    assert "scikit-learn" not in result["frequency"]


def test_consecutive_hyphens_are_not_valid_usernames(client):
    api, _ = client
    assert api.post("/api/analyze", data={**BASE, "github_username": "bad--user"}).status_code == 400


@pytest.mark.parametrize("text,years", [
    ("Education\nUniversity 2018-2022", None),
    ("Experience\nJob A 2018-2022\nJob B 2020-2024\nEducation\n2010-2017", 6),
    ("Experience\nJob 2030-2035", None),
    ("5 years of professional experience", 5),
])
def test_experience_is_conservative(text, years):
    assert extraction.extract_from_resume_text(text)["experience_evidence"]["years"] == years


def test_contact_only_text_keeps_privacy_without_career_gaps(client):
    api, _ = client
    result = api.post("/api/analyze", data={**BASE, "linkedin_text": "Phone: +1 555-0199"}).json()
    assert result["gap_analysis"]["skill_evidence_status"] == "insufficient_evidence"
    assert result["gap_analysis"]["experience_evidence_status"] == "unknown"
    assert any(item["rule_id"].startswith("R10-privacy") for item in result["recommendations"])
    assert not any(item["rule_id"].startswith(("R1-", "R2-", "R3-")) for item in result["recommendations"])


def test_linkedin_experience_is_used_without_summing_duplicate_sources():
    resume = extraction.extract_from_resume_text("3 years of experience in Python")
    linkedin = extraction.extract_from_linkedin_text("3 years of experience in Python")
    profile = identity_construction.build_digital_identity_profile(resume, {}, linkedin)
    assert profile["experience_evidence"]["years"] == 3
