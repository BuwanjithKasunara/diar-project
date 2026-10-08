"""
Explainable AI (XAI) Module
------------------------------
Every recommendation carries a rule-derived explanation (see recommendation_engine.py).
This module builds a top-level narrative summary explaining why the report looks the way
it does, tying together benchmark comparison, fuzzy classifications, contextual polarity,
insufficient evidence notices, and machine learning role predictions.
"""


def build_explanation_summary(profile: dict, benchmark_name: str, gap_analysis: dict,
                               visibility_assessment: dict, recommendations: list,
                               ml_prediction: dict = None) -> dict:
    skill_label = gap_analysis["skill_match_label"]
    completeness_label = gap_analysis["profile_completeness_label"]
    activity_label = gap_analysis["github_activity_label"]
    multi_factor = gap_analysis.get("multi_factor_score", gap_analysis.get("skill_match_score"))

    narrative_parts = [
        f"Compared against the '{benchmark_name}' benchmark identity, the current digital identity shows "
        f"a '{skill_label}' skill match (multi-factor score {multi_factor}), based on "
        f"{len(gap_analysis['matched_skills'])} matched skill(s) and "
        f"{len(gap_analysis['missing_required_skills'])} missing required skill(s).",

        f"Profile completeness across resume, GitHub, and LinkedIn is classified as '{completeness_label}' "
        f"(score {gap_analysis['profile_completeness_score']}).",
    ]

    if activity_label == "insufficient_evidence":
        coverage = profile.get("github", {}).get("repository_coverage")
        narrative_parts.append(
            "GitHub repository judgements were withheld because only part of the public portfolio was retrieved."
            if coverage == "limited" else
            "GitHub repository judgements were withheld because repository data was not supplied or could not be retrieved."
        )
    else:
        narrative_parts.append(
            f"GitHub activity is classified as '{activity_label}' (score {gap_analysis['github_activity_score']}), "
            f"based on repository update recency."
        )

    planned = gap_analysis.get("planned_skills", [])
    if planned:
        narrative_parts.append(
            f"Learning trajectory recognized: {len(planned)} skill(s) ({', '.join(planned[:3])}) detected as planned/in-progress."
        )

    negated = gap_analysis.get("negated_skills", [])
    if negated:
        narrative_parts.append(
            f"Context-aware NLP filtered out {len(negated)} explicitly negated skill(s) ({', '.join(negated[:3])}) to prevent false positive matching."
        )

    if ml_prediction and ml_prediction.get("model_available"):
        pred_role = ml_prediction.get("predicted_role")
        conf = (ml_prediction.get("confidence") or 0.0) * 100
        if ml_prediction.get("matches_target"):
            narrative_parts.append(
                f"The Supervised Machine Learning classifier confirms alignment, predicting your profile aligns with '{pred_role}' ({conf:.1f}% confidence)."
            )
        elif pred_role and pred_role != "Undetermined":
            narrative_parts.append(
                f"The Supervised Machine Learning classifier evaluated your profile text and predicted closest alignment with '{pred_role}' ({conf:.1f}% confidence) rather than '{benchmark_name}', indicating an opportunity to highlight more benchmark-specific skills and project terms."
            )

    if visibility_assessment.get("findings"):
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
