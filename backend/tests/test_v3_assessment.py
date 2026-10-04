import copy
import json

import pytest

from app import main
from app.modules import alignment_engine, extraction, identity_construction, planner, recommendation_engine


def missing_source(name):
    return {"source": name, "source_status": extraction.status("not_supplied")}


def profile_from_text(text, *, source="linkedin"):
    supplied = extraction.extract_text(text, source, "unverified")
    sources = {
        "resume": missing_source("resume"),
        "github": missing_source("github"),
        "linkedin": missing_source("linkedin"),
    }
    sources[source] = supplied
    return identity_construction.build_digital_identity_profile(
        sources["resume"], sources["github"], sources["linkedin"]
    )


def assess(text, role="AI Engineer", *, source="linkedin"):
    profile = profile_from_text(text, source=source)
    aligned = alignment_engine.run_alignment(
        profile,
        main.BENCHMARKS[role],
        role,
        "Privacy Focused",
    )
    return profile, aligned


def capabilities(aligned):
    return {
        result["id"]: result
        for result in aligned["assessment"]["benchmark_evidence"]["capability_results"]
    }


@pytest.mark.parametrize("tool", ["PyTorch", "TensorFlow"])
def test_model_tooling_accepts_framework_alternatives(tool):
    _, aligned = assess(f"Skills: Python, {tool}")
    tooling = capabilities(aligned)["model-tooling"]

    assert tooling["state"] == "evidenced"
    assert tooling["strength"] == 0.8
    assert tooling["matched_skills"] == [tool.lower()]
    assert len(tooling["evidence_ids"]) == 1


def test_model_tooling_alternatives_have_equal_weighted_effect():
    _, pytorch = assess("Skills: Python, PyTorch")
    _, tensorflow = assess("Skills: Python, TensorFlow")
    assert pytorch["assessment"]["benchmark_evidence"]["score"] == tensorflow["assessment"]["benchmark_evidence"]["score"]


def test_llm_evidence_does_not_invent_data_or_delivery_capability():
    _, aligned = assess("Projects: Built and evaluated a large language model experiment.")
    by_id = capabilities(aligned)

    assert by_id["ai-specialization"]["state"] == "evidenced"
    assert by_id["ai-specialization"]["matched_skills"] == ["llm"]
    assert by_id["delivery"]["state"] == "not_observed"
    assert by_id["delivery"]["matched_skills"] == []
    assert by_id["data-systems"]["state"] == "not_observed"
    assert by_id["data-systems"]["matched_skills"] == []


def test_inline_project_heading_is_retained_as_project_evidence():
    profile, aligned = assess("Skills: Python. Projects: Built a model evaluation service.")

    assert profile["project_evidence"] == [
        {"source": "linkedin", "excerpt": "Built a model evaluation service."}
    ]
    assert all(rule["id"] != "R4-project-evidence" for rule in aligned["fired_rules"])


def test_typo_evidence_is_weak_and_capped_at_half_strength():
    profile, aligned = assess("Skills: Pythom")
    programming = capabilities(aligned)["programming"]

    assert profile["evidence"][0]["method"] == "typo"
    assert profile["evidence"][0]["strength"] == 0.5
    assert programming["state"] == "weakly_evidenced"
    assert programming["strength"] == 0.5


def test_duplicate_keywords_do_not_accumulate_score_or_evidence_strength():
    _, once = assess("Skills: Python, PyTorch")
    _, repeated = assess("Skills: Python, Python, Python, PyTorch, PyTorch, PyTorch")

    once_summary = once["assessment"]["benchmark_evidence"]
    repeated_summary = repeated["assessment"]["benchmark_evidence"]
    assert once_summary["score"] == repeated_summary["score"]
    assert [(r["id"], r["state"], r["strength"]) for r in once_summary["capability_results"]] == [
        (r["id"], r["state"], r["strength"]) for r in repeated_summary["capability_results"]
    ]


def test_source_scope_is_separate_from_benchmark_evidence():
    profile, aligned = assess("Skills: Python")
    profile["source_statuses"]["github"] = extraction.status("partial", "One README unavailable.")
    profile["source_statuses"]["resume"] = extraction.status("failed", "Unreadable PDF.")
    aligned = alignment_engine.run_alignment(
        profile, main.BENCHMARKS["AI Engineer"], "AI Engineer", "Privacy Focused"
    )

    scope = aligned["assessment"]["source_scope"]
    assert scope == {
        "supported_total": 3,
        "usable_count": 2,
        "usable": ["github", "linkedin"],
        "partial": ["github"],
        "failed": ["resume"],
        "not_supplied": [],
    }
    assert aligned["assessment"]["benchmark_evidence"]["score"] is not None


def test_no_usable_source_marks_every_capability_not_assessed():
    profile = identity_construction.build_digital_identity_profile(
        missing_source("resume"), missing_source("github"), missing_source("linkedin")
    )
    aligned = alignment_engine.run_alignment(
        profile, main.BENCHMARKS["AI Engineer"], "AI Engineer", "Privacy Focused"
    )
    summary = aligned["assessment"]["benchmark_evidence"]

    assert summary["score"] is None
    assert summary["memberships"] == {}
    assert {result["state"] for result in summary["capability_results"]} == {"not_assessed"}


def test_absence_only_creates_documentation_actions_not_learning_actions():
    profile, aligned = assess("Skills: Python")
    recommendations = recommendation_engine.generate_recommendations(aligned["fired_rules"])
    generated = planner.generate_plan(
        aligned["objectives"],
        "AI Engineer",
        "Privacy Focused",
        profile["skills"],
        recommendations,
    )

    assert capabilities(aligned)["delivery"]["state"] == "not_observed"
    assert any(item["rule_id"] == "R1-evidence" for item in recommendations)
    assert all("learn" not in rule["action"].lower() for rule in aligned["fired_rules"])
    assert all(not step["id"].startswith("learn:") for step in generated["steps"])
    assert all("certif" not in json.dumps(item).lower() for item in recommendations)
    assert "inactive" not in json.dumps({"aligned": aligned, "recommendations": recommendations}).lower()


def test_only_an_explicit_negative_creates_development_recommendation():
    _, explicit = assess("Skills: Python. I have no experience with Docker.")
    _, planned = assess("Skills: Python. I plan to learn Docker.")

    assert capabilities(explicit)["delivery"]["state"] == "explicit_gap"
    assert any(rule["action"].startswith("recommend_learning:") for rule in explicit["fired_rules"])
    assert capabilities(planned)["delivery"]["state"] == "not_observed"
    assert all(not rule["action"].startswith("recommend_learning:") for rule in planned["fired_rules"])


def test_non_ai_roles_keep_required_preferred_seventy_thirty_weighting():
    for role in ("Software Engineer", "Data Scientist", "Researcher", "Entrepreneur"):
        groups = alignment_engine.benchmark_capabilities(main.BENCHMARKS[role])
        required = sum(group["weight"] for group in groups if group["importance"] == "required")
        preferred = sum(group["weight"] for group in groups if group["importance"] == "preferred")
        assert required == pytest.approx(0.7)
        assert preferred == pytest.approx(0.3)


def github_profile(repo_count, recent_count, last_push):
    github = {
        "source": "github",
        "source_status": extraction.status("analysed"),
        "skills": ["python"],
        "evidence": extraction.extract_evidence(
            "Skills: Python", "github", "repository_description", "synthetic-ai/repo", 0.8, False
        ),
        "repo_count": repo_count,
        "recently_pushed_owned_repo_count": recent_count,
        "last_owned_repository_push_at": last_push,
        "activity_window_days": 180,
        "languages": ["python"],
    }
    return identity_construction.build_digital_identity_profile(
        missing_source("resume"), github, missing_source("linkedin")
    )


def test_adding_stale_repositories_changes_only_raw_inventory_not_a_grade():
    recent_only = github_profile(1, 1, "2025-12-01T00:00:00+00:00")
    with_stale = github_profile(101, 1, "2025-12-01T00:00:00+00:00")

    first = alignment_engine.run_alignment(
        recent_only, main.BENCHMARKS["AI Engineer"], "AI Engineer", "Privacy Focused"
    )["assessment"]
    second = alignment_engine.run_alignment(
        with_stale, main.BENCHMARKS["AI Engineer"], "AI Engineer", "Privacy Focused"
    )["assessment"]

    assert first["benchmark_evidence"] == second["benchmark_evidence"]
    assert first["github_portfolio_recency"]["recently_pushed_owned_repository_count"] == 1
    assert second["github_portfolio_recency"]["recently_pushed_owned_repository_count"] == 1
    assert first["github_portfolio_recency"]["owned_public_non_fork_repository_count"] == 1
    assert second["github_portfolio_recency"]["owned_public_non_fork_repository_count"] == 101
    assert "label" not in first["github_portfolio_recency"]
    assert "score" not in first["github_portfolio_recency"]


def test_followers_are_not_an_input_to_benchmark_evidence():
    base = github_profile(1, 1, "2025-12-01T00:00:00+00:00")
    popular = copy.deepcopy(base)
    base["github"]["followers"] = 0
    popular["github"]["followers"] = 10_000_000

    first = alignment_engine.run_alignment(
        base, main.BENCHMARKS["AI Engineer"], "AI Engineer", "Privacy Focused"
    )["assessment"]["benchmark_evidence"]
    second = alignment_engine.run_alignment(
        popular, main.BENCHMARKS["AI Engineer"], "AI Engineer", "Privacy Focused"
    )["assessment"]["benchmark_evidence"]
    assert first == second

