"""
Digital Identity Alignment Engine
------------------------------------
Core reasoning component. Combines Rule-Based Reasoning with Fuzzy
Logic degrees (from fuzzy_logic.py) and a Multi-Factor Contextual Scoring
model to compare the user's Digital Identity Profile against the selected
Benchmark Identity, taking the user's preferred visibility level into account.

Enhancements:
- Multi-factor scoring incorporating claimed, uncertain, and planned skill weights.
- Explicit source state tracking (insufficient evidence detection).
- GitHub recency and stale codebase penalties.
- Negation and planned-intent aware rule generation.
    - Source-aware online-exposure advice.
"""
from typing import Dict, Any, List, Set
from . import fuzzy_logic
from . import privacy_assessment as privacy_engine

VISIBILITY_LEVELS = ["Fully Public", "Semi-Public", "Privacy Focused"]


def run_alignment(profile: dict, benchmark: dict, benchmark_name: str, visibility_level: str,
                  privacy_evidence: dict = None) -> dict:
    fired_rules: List[Dict[str, Any]] = []

    # 1. Retrieve Contextual Skills
    ctx = profile.get("contextual_skills", {})
    claimed_skills = set(ctx.get("claimed", profile.get("skills", [])))
    uncertain_skills = set(ctx.get("uncertain", []))
    planned_skills = set(ctx.get("planned", []))
    negated_skills = set(ctx.get("negated", []))
    norm_weights = ctx.get("normalized_weights", {})

    active_user_skills = claimed_skills | uncertain_skills
    skill_evidence_available = profile.get("skill_evidence_status") != "insufficient_evidence"

    required_skills = set(benchmark.get("required_skills", []))
    preferred_skills = set(benchmark.get("preferred_skills", []))

    missing_required = sorted(required_skills - active_user_skills)
    missing_preferred = sorted(preferred_skills - active_user_skills)
    matched_skills = sorted(active_user_skills & (required_skills | preferred_skills))

    # 2. Multi-Factor Contextual Scoring Engine
    total_req_points = 0.0
    earned_req_points = 0.0
    for r in required_skills:
        w = norm_weights.get(r, 1.0)
        total_req_points += 1.0 * w
        if r in claimed_skills:
            earned_req_points += 1.0 * w
        elif r in uncertain_skills:
            earned_req_points += 0.5 * w
        elif r in planned_skills:
            earned_req_points += 0.25 * w  # trajectory credit for learning intent
        elif r in negated_skills:
            earned_req_points += 0.0

    total_pref_points = 0.0
    earned_pref_points = 0.0
    for p in preferred_skills:
        w = norm_weights.get(p, 1.0)
        total_pref_points += 0.5 * w
        if p in claimed_skills:
            earned_pref_points += 0.5 * w
        elif p in uncertain_skills:
            earned_pref_points += 0.25 * w
        elif p in planned_skills:
            earned_pref_points += 0.125 * w

    denom = (total_req_points + total_pref_points) or 1.0
    multi_factor_score = round(min(1.0, (earned_req_points + earned_pref_points) / denom), 3)

    # Fuzzy logic match degree
    fuzzy_skill_score, fuzzy_skill_label = fuzzy_logic.skill_match_degree(
        active_user_skills, required_skills, preferred_skills
    )

    # 3. Context-Aware Rule Group 1: Skill Gap Rules
    for skill in missing_required if skill_evidence_available else []:
        if skill in planned_skills:
            fired_rules.append({
                "id": f"R1-planned-{skill}",
                "condition": f"benchmark='{benchmark_name}' AND required skill '{skill}' marked as planned",
                "action": f"accelerate_learning:{skill}",
                "priority": "high",
                "reason": f"You noted a plan to learn '{skill}'. Prioritizing this will directly resolve a required competency for '{benchmark_name}'."
            })
        elif skill in negated_skills:
            fired_rules.append({
                "id": f"R1-negated-{skill}",
                "condition": f"benchmark='{benchmark_name}' AND required skill '{skill}' explicitly negated",
                "action": f"structured_training:{skill}",
                "priority": "high",
                "reason": f"Your profile explicitly noted lack of experience in '{skill}', which is mandatory for '{benchmark_name}'."
            })
        else:
            fired_rules.append({
                "id": f"R1-{skill}",
                "condition": f"benchmark='{benchmark_name}' AND required skill '{skill}' not detected",
                "action": f"recommend_learning:{skill}",
                "priority": "high",
                "reason": f"'{skill}' is required for '{benchmark_name}' but was not detected in the supplied information. If you already have this skill, add relevant evidence; otherwise consider learning it."
            })

    for skill in missing_preferred if skill_evidence_available else []:
        if skill in planned_skills:
            fired_rules.append({
                "id": f"R2-planned-{skill}",
                "condition": f"benchmark='{benchmark_name}' AND preferred skill '{skill}' marked as planned",
                "action": f"continue_learning:{skill}",
                "priority": "medium",
                "reason": f"'{skill}' is a preferred skill that you plan to learn; this will strengthen your competitive edge."
            })
        else:
            fired_rules.append({
                "id": f"R2-{skill}",
                "condition": f"benchmark='{benchmark_name}' AND preferred skill '{skill}' not detected",
                "action": f"recommend_learning:{skill}",
                "priority": "medium",
                "reason": f"'{skill}' is preferred for '{benchmark_name}' but was not detected in the supplied information. Add evidence if you have it, or consider developing it."
            })

    # Rule Group 2: Experience rules
    min_years = benchmark.get("min_experience_years", 0)
    years = profile.get("estimated_years_experience", 0)
    experience_known = profile.get("experience_evidence", {}).get("status", "estimated") != "unknown"
    if experience_known and years < min_years:
        fired_rules.append({
            "id": "R3-experience",
            "condition": f"estimated_experience({years}y) < benchmark_min({min_years}y)",
            "action": "recommend_gaining_experience",
            "priority": "medium",
            "reason": f"The benchmark '{benchmark_name}' typically expects at least {min_years} year(s) of relevant experience; the profile suggests approximately {years}."
        })

    # Rule Group 3: GitHub Activity, Recency & State Tracking
    github_data = profile.get("github", {})
    gh_state = github_data.get("state", "not_supplied")
    repository_state = github_data.get("repository_state", gh_state)
    repo_count = github_data.get("repo_count", 0)
    active_count = github_data.get("recently_active_repo_count", 0)
    stale_count = github_data.get("stale_repo_count", 0)
    min_repos = benchmark.get("min_github_repos", 0)

    if repository_state != "analysed":
        activity_score = 0.0
        activity_label = "insufficient_evidence"
        if gh_state in ("not_supplied", "failed"):
            focus_mode = visibility_level == "Privacy Focused"
            fired_rules.append({
                "id": "R4-github-insufficient-evidence",
                "condition": f"github_source_state='{gh_state}'",
                "action": "skip_github_analysis" if focus_mode else "provide_github_profile",
                "priority": "low" if focus_mode else "high",
                "reason": "GitHub evidence was not supplied. You can skip it or provide the public username only if comfortable; private repositories cannot be reviewed through this lookup." if focus_mode else "GitHub profile evidence is unavailable. Supply a username, check it for errors, or retry the analysis."
            })
        elif repository_state == "failed":
            fired_rules.append({
                "id": "R4-github-repositories-unavailable",
                "condition": "github_profile_available AND github_repository_state='failed'",
                "action": "retry_github_analysis",
                "priority": "medium",
                "reason": "The GitHub profile loaded, but its repository data is unavailable. Retry before assessing repository count, activity, or language diversity."
            })
    else:
        activity_score, activity_label = fuzzy_logic.activity_degree(active_count, max(repo_count, 1))

        if repo_count < min_repos:
            action = {
                "Fully Public": "recommend_building_portfolio_projects",
                "Semi-Public": "recommend_curating_portfolio",
                "Privacy Focused": "recommend_private_portfolio_projects",
            }.get(visibility_level, "recommend_building_portfolio_projects")
            reason = {
                "Fully Public": f"'{benchmark_name}' benchmark profiles typically showcase at least {min_repos} public repositories; this GitHub profile has {repo_count}.",
                "Semi-Public": f"The '{benchmark_name}' benchmark suggests more portfolio evidence. Develop projects and choose which ones you want to showcase publicly; others can stay private.",
                "Privacy Focused": f"The '{benchmark_name}' benchmark suggests more portfolio evidence. You can develop projects privately and share selected evidence directly; additional public repositories are optional.",
            }.get(visibility_level)
            fired_rules.append({
                "id": "R4-repo-count",
                "condition": f"github_repo_count({repo_count}) < benchmark_min({min_repos})",
                "action": action,
                "priority": "high",
                "reason": reason
            })

        if stale_count > 0 and active_count == 0 and repo_count > 0:
            action = "recommend_refreshing_repos" if visibility_level == "Fully Public" else (
                "recommend_refreshing_selected_repos" if visibility_level == "Semi-Public" else "recommend_refreshing_private_repos"
            )
            reason = "Repository recency analysis indicates all public repositories are stale (>1-2 years without updates). Pushing fresh code or open-source commits will demonstrate active engagement." if visibility_level == "Fully Public" else (
                "Selected public repositories may benefit from an update; other projects can remain private." if visibility_level == "Semi-Public" else
                "Relevant portfolio work may benefit from updates. Public commit activity is optional; share only selected evidence."
            )
            fired_rules.append({
                "id": "R5-stale-codebases",
                "condition": f"github_stale_repos={stale_count} AND active_recent=0",
                "action": action,
                "priority": "high",
                "reason": reason
            })
        elif activity_label == "inactive" and repo_count > 0:
            action = "recommend_increasing_github_activity" if visibility_level == "Fully Public" else (
                "recommend_refreshing_selected_repos" if visibility_level == "Semi-Public" else "recommend_refreshing_private_repos"
            )
            fired_rules.append({
                "id": "R5-activity",
                "condition": f"github_activity_degree={activity_score} -> '{activity_label}'",
                "action": action,
                "priority": "medium",
                "reason": "Recent GitHub activity is classified as 'inactive', which can weaken perceived engagement. Public commit activity is optional; keep relevant work current privately and share only selected evidence." if visibility_level == "Privacy Focused" else "Recent activity in selected repositories could be refreshed; other projects can remain private." if visibility_level == "Semi-Public" else "Recent GitHub activity is classified as 'inactive', which can weaken perceived engagement."
            })

        min_langs = benchmark.get("min_github_languages", 0)
        langs = len(github_data.get("languages", []))
        if langs < min_langs:
            language_action = {
                "Fully Public": "recommend_diversifying_projects",
                "Semi-Public": "recommend_diversifying_selected_projects",
                "Privacy Focused": "recommend_diversifying_private_projects",
            }.get(visibility_level, "recommend_diversifying_projects")
            fired_rules.append({
                "id": "R6-languages",
                "condition": f"github_language_diversity({langs}) < benchmark_min({min_langs})",
                "action": language_action,
                "priority": "low",
                "reason": f"Benchmark identities typically demonstrate at least {min_langs} distinct programming languages; {langs} were detected. Add language breadth to your work; public sharing is optional." if visibility_level == "Privacy Focused" else f"Benchmark identities typically demonstrate at least {min_langs} distinct programming languages; {langs} were detected. Develop projects and choose which ones to showcase." if visibility_level == "Semi-Public" else f"Benchmark identities typically demonstrate at least {min_langs} distinct programming languages; {langs} detected."
            })

    # Rule Group 4: Certifications
    if not profile.get("insufficient_evidence") and not profile.get("certifications") and benchmark.get("certifications"):
        fired_rules.append({
            "id": "R7-certifications",
            "condition": "no certifications detected AND benchmark defines relevant certifications",
            "action": "recommend_certification",
            "priority": "medium",
            "reason": f"No certifications detected. Relevant options for '{benchmark_name}' include: {', '.join(benchmark.get('certifications', [])[:3])}."
        })

    # Rule Group 5: Completeness Rules
    source_states = profile.get("source_states", {})
    completeness_score, completeness_label = fuzzy_logic.completeness_degree(profile.get("completeness_flags", {}))

    if source_states.get("linkedin") == "not_supplied":
        linkedin_action = "skip_linkedin_analysis" if visibility_level == "Privacy Focused" else "provide_linkedin_for_analysis"
        fired_rules.append({
            "id": "R9-missing-linkedin",
            "condition": "linkedin_state='not_supplied'",
            "action": linkedin_action,
            "priority": "medium",
            "reason": "No LinkedIn text was supplied. Paste relevant text only if you want that source included in the analysis; this does not mean you lack a LinkedIn account or need to publish more information." if visibility_level != "Privacy Focused" else "LinkedIn analysis is optional. You can skip it or supply text only if comfortable; a public profile is not required."
        })

    # Rule Group 6: Source-aware privacy evidence and visibility goals.
    contact_exposed = profile.get("public_contact_info_detected", False)
    visibility_assessment = privacy_engine.assess_visibility(privacy_evidence or {}, visibility_level)
    fired_rules.extend(visibility_assessment["rules"])

    if visibility_level == "Fully Public":
        if completeness_label != "complete":
            fired_rules.append({
                "id": "R11-visibility-incomplete",
                "condition": f"visibility='Fully Public' AND completeness='{completeness_label}'",
                "action": "recommend_maximising_profile_completeness",
                "priority": "medium",
                "reason": "Only some source information was supplied. Add relevant evidence from your chosen sources if you want a broader assessment; actual account completeness was not verified."
            })
            visibility_assessment["findings"].append("Source coverage is incomplete; actual account completeness was not verified.")
        else:
            visibility_assessment["findings"].append("All three source types were supplied for this assessment; actual account completeness was not verified.")

    gap_analysis = {
        "missing_required_skills": missing_required,
        "missing_preferred_skills": missing_preferred,
        "matched_skills": matched_skills,
        "claimed_skills": list(claimed_skills),
        "uncertain_skills": list(uncertain_skills),
        "planned_skills": list(planned_skills),
        "negated_skills": list(negated_skills),
        "multi_factor_score": multi_factor_score,
        "skill_evidence_status": "observed" if skill_evidence_available else "insufficient_evidence",
        "experience_evidence_status": "estimated" if experience_known else "unknown",
        "skill_match_score": fuzzy_skill_score,
        "skill_match_label": fuzzy_skill_label,
        "github_activity_score": activity_score,
        "github_activity_label": activity_label,
        "profile_completeness_score": completeness_score,
        "profile_completeness_label": completeness_label,
    }

    visibility_assessment.update({"selected_level": visibility_level,
                                  "public_contact_info_detected": contact_exposed})

    return {
        "gap_analysis": gap_analysis,
        "visibility_assessment": visibility_assessment,
        "fired_rules": fired_rules,
    }
