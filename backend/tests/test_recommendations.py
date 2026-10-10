"""Regression coverage for recommendation wording, ranking, and deduplication."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.modules.recommendation_engine import generate_recommendations


def _rule(action, priority="high", rule_id="test-rule"):
    return {
        "id": rule_id,
        "action": action,
        "priority": priority,
        "reason": f"Evidence for {rule_id}",
    }


def test_navigation_categories_preserve_ranking_and_visibility_evidence():
    career = _rule("develop_skill:python", "high", "career-test")
    privacy = {**_rule("review_privacy_detail", "medium", "privacy-test"),
               "category": "visibility", "source": "github_repository_file",
               "evidence_ids": ["synthetic-evidence"]}
    result = generate_recommendations([privacy, career])
    assert [rec["rule_id"] for rec in result] == ["career-test", "privacy-test"]
    assert result[0]["category"] == "career"
    assert result[1]["category"] == "visibility"
    assert result[1]["evidence_ids"] == ["synthetic-evidence"]


@pytest.mark.parametrize(
    "action, expected",
    [
        ("accelerate_learning:docker", "Prioritise learning skill: docker"),
        ("structured_training:c++", "Complete structured training in: c++"),
        ("continue_learning:machine learning", "Continue learning skill: machine learning"),
        ("provide_github_profile", "Provide a valid GitHub profile for analysis"),
        (
            "recommend_refreshing_github_repos",
            "Refresh older GitHub repositories with relevant updates",
        ),
        ("recommend_learning:python", "Develop skill: python"),
    ],
)
def test_recommendations_have_readable_labels_and_preserve_skills(action, expected):
    recommendation = generate_recommendations([_rule(action)])[0]

    assert recommendation["recommendation"] == expected
    assert recommendation["rule_id"] == "test-rule"
    assert recommendation["explanation"] == "Evidence for test-rule"


@pytest.mark.parametrize(
    "action, expected",
    [
        ("review_portfolio", "Review portfolio"),
        ("review_skill:machine learning", "Review skill: machine learning"),
        ("review_resource:https://example.com", "Review resource: https://example.com"),
    ],
)
def test_unknown_actions_keep_readable_names_and_complete_arguments(action, expected):
    recommendation = generate_recommendations([_rule(action)])[0]

    assert recommendation["recommendation"] == expected


def test_ranking_keeps_highest_priority_duplicate_and_stable_ties():
    rules = [
        _rule("recommend_learning:python", "low", "low-python"),
        _rule("continue_learning:docker", "high", "high-docker"),
        _rule("recommend_learning:python", "high", "high-python"),
        _rule("recommend_certification", "medium", "medium-certification"),
    ]

    recommendations = generate_recommendations(rules)

    assert [item["rule_id"] for item in recommendations] == [
        "high-docker", "high-python", "medium-certification"
    ]
    assert [item["rank"] for item in recommendations] == [1, 2, 3]
    assert recommendations[1]["explanation"] == "Evidence for high-python"
