"""
Digital Identity Alignment Engine
------------------------------------
Core reasoning component. Combines Rule-Based Reasoning with Fuzzy
Logic degrees (from fuzzy_logic.py) to compare the user's Digital
Identity Profile against the selected Benchmark Identity, taking the
user's preferred visibility level into account.

Every fired rule is recorded with a machine-readable "id" and a
human-readable "reason" so the Explainable AI Module can trace every
recommendation back to the rule(s) that produced it.
"""
from . import fuzzy_logic

VISIBILITY_LEVELS = ["Fully Public", "Semi-Public", "Privacy Focused"]


def run_alignment(profile: dict, benchmark: dict, benchmark_name: str, visibility_level: str) -> dict:
    fired_rules = []

    user_skills = set(profile.get("skills", []))
    required_skills = set(benchmark.get("required_skills", []))
    preferred_skills = set(benchmark.get("preferred_skills", []))

    missing_required = sorted(required_skills - user_skills)
    missing_preferred = sorted(preferred_skills - user_skills)
    matched_skills = sorted(user_skills & (required_skills | preferred_skills))

    skill_score, skill_label = fuzzy_logic.skill_match_degree(user_skills, required_skills, preferred_skills)

    # --- Rule Group 1: Skill gap rules ---
    for skill in missing_required:
        fired_rules.append({
            "id": f"R1-{skill}",
            "condition": f"benchmark='{benchmark_name}' AND required skill '{skill}' not detected",
            "action": f"recommend_learning:{skill}",
            "priority": "high",
            "reason": f"'{skill}' is a required skill for the '{benchmark_name}' benchmark and was not "
                      f"found in the user's resume, GitHub, or LinkedIn data."
        })
    for skill in missing_preferred:
        fired_rules.append({
            "id": f"R2-{skill}",
            "condition": f"benchmark='{benchmark_name}' AND preferred skill '{skill}' not detected",
            "action": f"recommend_learning:{skill}",
            "priority": "medium",
            "reason": f"'{skill}' is a preferred (non-mandatory) skill for '{benchmark_name}' that would "
                      f"strengthen the profile if added."
        })

    # --- Rule Group 2: Experience rules ---
    min_years = benchmark.get("min_experience_years", 0)
    years = profile.get("estimated_years_experience", 0)
    if years < min_years:
        fired_rules.append({
            "id": "R3-experience",
            "condition": f"estimated_experience({years}y) < benchmark_min({min_years}y)",
            "action": "recommend_gaining_experience",
            "priority": "medium",
            "reason": f"The benchmark '{benchmark_name}' typically expects at least {min_years} year(s) of "
                      f"relevant experience; the resume suggests approximately {years}."
        })

    # --- Rule Group 3: GitHub project / activity rules (fuzzy) ---
    repo_count = profile.get("github", {}).get("repo_count", 0)
    active_count = profile.get("github", {}).get("recently_active_repo_count", 0)
    min_repos = benchmark.get("min_github_repos", 0)
    activity_score, activity_label = fuzzy_logic.activity_degree(active_count, max(repo_count, 1))

    if repo_count < min_repos:
        fired_rules.append({
            "id": "R4-repo-count",
            "condition": f"github_repo_count({repo_count}) < benchmark_min({min_repos})",
            "action": "recommend_building_portfolio_projects",
            "priority": "high",
            "reason": f"'{benchmark_name}' benchmark profiles typically showcase at least {min_repos} "
                      f"public repositories; this GitHub profile has {repo_count}."
        })
    if activity_label == "inactive" and repo_count > 0:
        fired_rules.append({
            "id": "R5-activity",
            "condition": f"github_activity_degree={activity_score} -> '{activity_label}'",
            "action": "recommend_increasing_github_activity",
            "priority": "medium",
            "reason": "Fuzzy analysis classifies recent GitHub activity as 'inactive' "
                      "(few or no repositories updated recently), which can weaken perceived engagement."
        })

    min_langs = benchmark.get("min_github_languages", 0)
    langs = len(profile.get("github", {}).get("languages", []))
    if langs < min_langs:
        fired_rules.append({
            "id": "R6-languages",
            "condition": f"github_language_diversity({langs}) < benchmark_min({min_langs})",
            "action": "recommend_diversifying_projects",
            "priority": "low",
            "reason": f"Benchmark identities in this field typically demonstrate at least {min_langs} "
                      f"distinct programming languages across repositories; {langs} detected."
        })

    # --- Rule Group 4: Certification rules ---
    if not profile.get("certifications") and benchmark.get("certifications"):
        fired_rules.append({
            "id": "R7-certifications",
            "condition": "no certifications detected AND benchmark defines relevant certifications",
            "action": "recommend_certification",
            "priority": "medium",
            "reason": f"No certifications were detected. Relevant options for '{benchmark_name}' include: "
                      f"{', '.join(benchmark.get('certifications', [])[:3])}."
        })

    # --- Rule Group 5: Profile completeness rules (fuzzy) ---
    completeness_score, completeness_label = fuzzy_logic.completeness_degree(profile.get("completeness_flags", {}))
    if not profile.get("completeness_flags", {}).get("github_provided"):
        fired_rules.append({
            "id": "R8-missing-github",
            "condition": "github_provided=False",
            "action": "recommend_adding_github",
            "priority": "high",
            "reason": "No GitHub profile was analysed. Technical benchmarks rely heavily on GitHub "
                      "evidence of hands-on project work."
        })
    if not profile.get("completeness_flags", {}).get("linkedin_provided"):
        fired_rules.append({
            "id": "R9-missing-linkedin",
            "condition": "linkedin_provided=False",
            "action": "recommend_completing_linkedin",
            "priority": "medium",
            "reason": "No usable LinkedIn profile text was provided or the profile appears too sparse "
                      "to analyse, limiting network-facing visibility."
        })

    # --- Rule Group 6: Visibility / privacy rules ---
    visibility_findings = []
    contact_exposed = profile.get("public_contact_info_detected", False)

    if visibility_level == "Privacy Focused" and contact_exposed:
        fired_rules.append({
            "id": "R10-privacy-contact",
            "condition": "visibility='Privacy Focused' AND contact_info_detected=True",
            "action": "recommend_reducing_public_contact_exposure",
            "priority": "high",
            "reason": "The user selected 'Privacy Focused' visibility, but contact information "
                      "(email/phone-like patterns) was detected in publicly analysable text."
        })
        visibility_findings.append("Public contact information detected despite a Privacy Focused preference.")

    if visibility_level == "Fully Public" and completeness_label != "complete":
        fired_rules.append({
            "id": "R11-visibility-incomplete",
            "condition": f"visibility='Fully Public' AND completeness='{completeness_label}'",
            "action": "recommend_maximising_profile_completeness",
            "priority": "medium",
            "reason": "A 'Fully Public' visibility preference works best with a complete profile across "
                      "all sources so recruiters see a consistent, strong identity."
        })
        visibility_findings.append("Profile is not yet fully complete despite a Fully Public visibility goal.")

    if visibility_level == "Semi-Public":
        visibility_findings.append("Balanced visibility selected: recommendations favour showcasing "
                                    "professional strengths while minimising personal contact exposure.")

    gap_analysis = {
        "missing_required_skills": missing_required,
        "missing_preferred_skills": missing_preferred,
        "matched_skills": matched_skills,
        "skill_match_score": skill_score,
        "skill_match_label": skill_label,
        "github_activity_score": activity_score,
        "github_activity_label": activity_label,
        "profile_completeness_score": completeness_score,
        "profile_completeness_label": completeness_label,
    }

    visibility_assessment = {
        "selected_level": visibility_level,
        "public_contact_info_detected": contact_exposed,
        "findings": visibility_findings,
    }

    return {
        "gap_analysis": gap_analysis,
        "visibility_assessment": visibility_assessment,
        "fired_rules": fired_rules,
    }
