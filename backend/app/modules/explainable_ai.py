"""
Explainable AI (XAI) Module
------------------------------
Every recommendation already carries a rule-derived explanation (see
recommendation_engine.py). This module adds a top-level narrative
summary of *why* the overall report looks the way it does, tying
together the benchmark comparison, fuzzy classifications, and the
user's visibility preference -- so the final report reads as a
coherent explanation rather than a bare list of scores.
"""


def build_explanation_summary(profile: dict, benchmark_name: str, gap_analysis: dict,
                               visibility_assessment: dict, recommendations: list) -> dict:
    skill_label = gap_analysis["skill_match_label"]
    completeness_label = gap_analysis["profile_completeness_label"]
    activity_label = gap_analysis["github_activity_label"]

    narrative_parts = [
        f"Compared against the '{benchmark_name}' benchmark identity, the current digital identity shows "
        f"a '{skill_label}' skill match (score {gap_analysis['skill_match_score']}), based on "
        f"{len(gap_analysis['matched_skills'])} matched skill(s) and "
        f"{len(gap_analysis['missing_required_skills'])} missing required skill(s).",

        f"Profile completeness across resume, GitHub, and LinkedIn is classified as '{completeness_label}' "
        f"(score {gap_analysis['profile_completeness_score']}).",

        f"GitHub activity is classified as '{activity_label}' (score {gap_analysis['github_activity_score']}), "
        f"based on the proportion of recently updated repositories.",
    ]

    if visibility_assessment["findings"]:
        narrative_parts.append(
            f"Regarding the selected '{visibility_assessment['selected_level']}' visibility preference: "
            + " ".join(visibility_assessment["findings"])
        )

    top_reasons = [r["explanation"] for r in recommendations[:3]]

    return {
        "narrative": " ".join(narrative_parts),
        "top_recommendation_reasons": top_reasons,
        "rules_fired_count": len(recommendations),
    }
