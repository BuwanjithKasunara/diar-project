"""
DIAR Automated Validation & Regression Test Suite
--------------------------------------------------
Validates all 7 core features:
1. Context-Aware Skill Categorization (claimed, planned, negated, uncertain)
2. Frequency Normalization & Noise Suppression (keyword stuffing protection)
3. Explicit Data Source State Tracking (insufficient evidence detection)
4. Multi-Factor Contextual Scoring Engine
5. Repository Recency & Domain Filtering
6. Granular Privacy & Visibility Redaction
7. Machine Learning Role Classifier Accuracy & Prediction Consistency
"""
import os
import sys

# Ensure backend root is on Python sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.modules import extraction, identity_construction, alignment_engine, ml_classifier
from app.main import app, sanitize_profile_for_visibility
from fastapi.testclient import TestClient

client = TestClient(app)


# -------------------------------------------------------------
# 1. Context-Aware Skill Categorization Tests
# -------------------------------------------------------------
def test_claimed_skill_detection():
    text = "Extensive 4 years experience with Python, PyTorch, and SQL."
    res = extraction.extract_contextual_skills(text)
    assert "python" in res["claimed"]
    assert "pytorch" in res["claimed"]
    assert "sql" in res["claimed"]
    assert len(res["negated"]) == 0
    assert len(res["planned"]) == 0


def test_negated_skill_detection():
    text = "Proficient in Python and FastAPI. No experience with Java or Docker."
    res = extraction.extract_contextual_skills(text)
    assert "python" in res["claimed"]
    assert "fastapi" in res["claimed"]
    assert "java" in res["negated"]
    assert "docker" in res["negated"]
    # Negated skills must NOT leak into claimed skills
    assert "java" not in res["claimed"]
    assert "docker" not in res["claimed"]


def test_planned_intent_skill_detection():
    text = "Skilled in Python and Scikit-learn. Plan to learn Kubernetes next quarter. Currently learning Docker."
    res = extraction.extract_contextual_skills(text)
    assert "python" in res["claimed"]
    assert "kubernetes" in res["planned"]
    assert "docker" in res["planned"]
    # Planned skills must NOT be counted as already claimed hands-on skills
    assert "kubernetes" not in res["claimed"]


def test_uncertain_skill_detection():
    text = "Strong in Python. Basic knowledge of AWS and elementary exposure to C++."
    res = extraction.extract_contextual_skills(text)
    assert "python" in res["claimed"]
    assert "aws" in res["uncertain"]


# -------------------------------------------------------------
# 2. Frequency Normalization & Anti-Keyword-Stuffing Tests
# -------------------------------------------------------------
def test_frequency_normalization_caps_repetition():
    text = "Python " * 15  # Candidate attempts keyword-stuffing
    res = extraction.extract_contextual_skills(text)
    assert res["frequency"]["python"] == 15
    # Normalized weight must be capped (saturation limit at min(count, 5))
    weight = res["normalized_weights"]["python"]
    assert weight <= 2.0  # Cannot grow unbounded


# -------------------------------------------------------------
# 3. Explicit Data Source State Tracking Tests
# -------------------------------------------------------------
def test_source_state_tracking_not_supplied():
    resume_data = extraction.extract_from_resume_text("")
    github_data = extraction.extract_from_github("")
    linkedin_data = extraction.extract_from_linkedin_text("")

    profile = identity_construction.build_digital_identity_profile(resume_data, github_data, linkedin_data)
    assert profile["source_states"]["resume"] == "not_supplied"
    assert profile["source_states"]["github"] == "not_supplied"
    assert profile["source_states"]["linkedin"] == "not_supplied"
    assert profile["insufficient_evidence"] is True


def test_source_state_tracking_analysed():
    resume_data = extraction.extract_from_resume_text(
        "Senior Software Engineer with 5 years experience in Python, Git, and PostgreSQL. Built scalable distributed systems."
    )
    assert resume_data["source_state"] == "analysed"
    assert resume_data["raw_text_length"] > 80


# -------------------------------------------------------------
# 4. Multi-Factor Contextual Scoring Engine Tests
# -------------------------------------------------------------
def test_multi_factor_scoring_penalizes_negations():
    benchmark = {
        "required_skills": ["python", "docker"],
        "preferred_skills": ["kubernetes"],
        "min_experience_years": 1,
        "min_github_repos": 0,
        "min_github_languages": 0,
    }

    # Case A: Claims Python, plans Docker
    profile_a = identity_construction.build_digital_identity_profile(
        extraction.extract_from_resume_text("Skilled in Python. Plan to learn Docker."),
        {"skills": [], "languages": [], "source_state": "not_supplied"},
        {"skills": [], "source_state": "not_supplied"}
    )
    res_a = alignment_engine.run_alignment(profile_a, benchmark, "Test Benchmark", "Fully Public")

    # Case B: Claims Python, explicitly negates Docker
    profile_b = identity_construction.build_digital_identity_profile(
        extraction.extract_from_resume_text("Skilled in Python. No experience in Docker."),
        {"skills": [], "languages": [], "source_state": "not_supplied"},
        {"skills": [], "source_state": "not_supplied"}
    )
    res_b = alignment_engine.run_alignment(profile_b, benchmark, "Test Benchmark", "Fully Public")

    # Case A should score higher than Case B because planned learning grants trajectory credit
    score_a = res_a["gap_analysis"]["multi_factor_score"]
    score_b = res_b["gap_analysis"]["multi_factor_score"]
    assert score_a > score_b


# -------------------------------------------------------------
# 5. Insufficient Evidence Activity Penalty Avoidance Tests
# -------------------------------------------------------------
def test_insufficient_evidence_withholds_activity_penalty():
    benchmark = {
        "required_skills": ["python"],
        "preferred_skills": [],
        "min_experience_years": 0,
        "min_github_repos": 3,
        "min_github_languages": 1,
    }
    # User provides resume but NO GitHub
    profile = identity_construction.build_digital_identity_profile(
        extraction.extract_from_resume_text("Experienced Python developer."),
        {"skills": [], "languages": [], "source_state": "not_supplied"},
        {"skills": [], "source_state": "not_supplied"}
    )
    res = alignment_engine.run_alignment(profile, benchmark, "Test", "Fully Public")

    # Activity must be labeled "insufficient_evidence", NOT "inactive"
    assert res["gap_analysis"]["github_activity_label"] == "insufficient_evidence"


# -------------------------------------------------------------
# 6. Granular Privacy & Visibility Redaction Tests
# -------------------------------------------------------------
def test_privacy_focused_redactions():
    raw_profile = {
        "github": {"username": "buwank", "bio": "Contact me at dev@example.com or +1234567890"},
        "resume": {"experience_snippet": "Email: personal@domain.com, Phone: +1 555-0199"},
        "linkedin": {"headline": "Founder at SecretCo - dev@example.com"}
    }
    sanitized = sanitize_profile_for_visibility(raw_profile, "Privacy Focused")
    assert sanitized["github"]["username"] == "[ANONYMOUS_USER]"
    assert "personal@domain.com" not in sanitized["resume"]["experience_snippet"]
    assert "[REDACTED_EMAIL]" in sanitized["resume"]["experience_snippet"]
    assert "+1 555-0199" not in sanitized["resume"]["experience_snippet"]


# -------------------------------------------------------------
# 7. Machine Learning Role Classifier Tests
# -------------------------------------------------------------
def test_ml_classifier_predictions():
    ai_text = "Machine Learning Engineer working on PyTorch, deep learning, computer vision, and neural networks."
    pred = ml_classifier.predict_role(ai_text, target_benchmark="AI Engineer")
    assert pred["model_available"] is True
    assert pred["predicted_role"] == "AI Engineer"
    assert pred["matches_target"] is True
    assert pred["confidence"] > 0.4


# -------------------------------------------------------------
# 8. End-to-End API Integration Test
# -------------------------------------------------------------
def test_analyze_api_end_to_end():
    response = client.post(
        "/api/analyze",
        data={
            "benchmark_identity": "AI Engineer",
            "visibility_level": "Fully Public",
            "linkedin_text": "Experienced in Python, Machine Learning, Deep Learning, PyTorch, and SQL. Plan to learn Docker."
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "digital_identity_profile" in data
    assert "ml_prediction" in data
    assert data["ml_prediction"]["predicted_role"] == "AI Engineer"
    assert "multi_factor_score" in data["gap_analysis"]
    assert "planned_skills" in data["gap_analysis"]
