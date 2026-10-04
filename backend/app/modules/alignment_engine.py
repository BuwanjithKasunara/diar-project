"""Evidence-aware rules. Unknown inputs are not treated as observed deficiencies."""
import re
from . import fuzzy_logic
VISIBILITY_LEVELS = ["Fully Public", "Semi-Public", "Privacy Focused"]


def run_alignment(profile, benchmark, benchmark_name, visibility_level):
    rules, clarification, goals = [], [], []
    skills = set(profile["skills"])
    required, preferred = set(benchmark["required_skills"]), set(benchmark["preferred_skills"])
    missing = sorted(required - skills)
    missing_preferred = sorted(preferred - skills)
    matched = sorted(skills & (required | preferred))
    score, label = fuzzy_logic.skill_match_degree(skills, required, preferred)
    if profile["sources_provided_count"] == 0:
        score, label = None, "insufficient evidence"

    def rule(id, action, title, priority, reason, objective=None):
        rules.append({"id": id, "action": action, "title": title, "priority": priority,
                      "condition": reason, "reason": reason, "objective": objective})
        if objective:
            goals.append(objective)

    if score is not None:
        for skill in missing:
            rule("R1-" + skill, "recommend_learning:" + skill, "Develop evidence of " + skill, "high",
                 f"'{skill}' is required by {benchmark_name}, but no positive claim was detected in the analysed sources. This is not proof of absent ability.",
                 "skill:" + skill)
        for skill in missing_preferred:
            rule("R2-" + skill, "recommend_learning:" + skill, "Consider " + skill, "medium",
                 f"'{skill}' is preferred by {benchmark_name}; no positive claim was detected.")
    years = profile["estimated_years_experience"]
    if years is None and benchmark.get("min_experience_years", 0):
        clarification.append("Supply clearly dated employment history to assess experience.")
    elif years is not None and years < benchmark.get("min_experience_years", 0):
        rule("R3-experience", "recommend_gaining_experience", "Gain relevant experience", "medium",
             f"Parsed employment periods suggest about {years} years; the benchmark expects {benchmark['min_experience_years']}.")

    repo = profile["github"]
    count, active = repo.get("repo_count"), repo.get("recently_active_repo_count")
    activity_score, activity_label = (None, "insufficient evidence")
    if count is not None and active is not None:
        activity_score, activity_label = fuzzy_logic.activity_degree(active, count)
    github_required = benchmark.get("github_required", True)
    project_text = " ".join(p["excerpt"] for p in profile["project_evidence"]).lower()
    project_matches = sorted({kw for kw in benchmark.get("expected_project_keywords", [])
                              if re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", project_text)})
    showcase = {"Fully Public": "Publish a relevant portfolio project",
                "Semi-Public": "Prepare a portfolio project for selective sharing",
                "Privacy Focused": "Prepare a private portfolio project"}[visibility_level]
    if github_required and count is None:
        clarification.append("GitHub counts/activity are unavailable; supply or retry the source if you want them assessed.")
    # A relevant project can be private. Repository counts do not override privacy choices.
    project_needed = not project_matches and profile["sources_provided_count"] > 0
    if project_needed:
        rule("R4-project", "recommend_portfolio", showcase, "high",
             f"No relevant project description was found for {benchmark_name}. {visibility_level} controls the suggested sharing method; keywords are only a relevance proxy.",
             "evidence:project")
    if github_required and count is not None and count < benchmark.get("min_github_repos", 0):
        rule("R4-repo-count", "recommend_portfolio", showcase, "medium",
             f"{count} non-fork repositories observed against the illustrative benchmark of {benchmark['min_github_repos']}. Private evidence is also acceptable.")
    if count and activity_label == "inactive" and github_required:
        rule("R5-activity", "recommend_activity", "Maintain relevant project evidence", "medium",
             "Recent push timestamps indicate low activity. This proxy does not measure contribution quality.")
    if github_required and count is not None and len(repo.get("languages") or []) < benchmark.get("min_github_languages", 0):
        rule("R6-languages", "recommend_diversity", "Consider broader project experience", "low",
             "Observed primary repository languages are below the illustrative benchmark; diversity alone does not establish competence.")

    relevant_certs = [c for c in profile["certifications"] if any(
        expected.lower() in c.lower() for expected in benchmark.get("certifications", []))]
    if not relevant_certs:
        rule("R7-certifications", "recommend_certification", "Consider a relevant certification", "medium",
             "No listed benchmark certification was matched. Exact-name matching is conservative; equivalent credentials may need review.")
    if not profile["completeness_flags"]["linkedin_provided"]:
        clarification.append("LinkedIn text was not analysed; it is optional and can be supplied for additional evidence.")

    public_contact = profile["public_contact_info_detected"]
    findings = []
    if public_contact and visibility_level != "Fully Public":
        rule("R10-privacy-contact", "recommend_privacy", "Reduce public contact exposure", "high",
             f"Contact information was detected in a source identified as public, conflicting with the {visibility_level} preference.",
             "privacy:contact")
        findings.append("Contact details detected in a public source; consider selective contact sharing.")
    if any(c["visibility"] == "unverified" for c in profile["contact_findings"]):
        findings.append("Contact details occur in text with unverified visibility; public exposure is not established.")
    if any(c["visibility"] == "private" for c in profile["contact_findings"]):
        findings.append("Contact details in private input are not treated as public exposure.")
    findings.append({"Fully Public": "Public showcase actions are permitted.",
                     "Semi-Public": "Suggested actions favour selective sharing.",
                     "Privacy Focused": "Suggested actions support private portfolios."}[visibility_level])
    completeness, completeness_label = fuzzy_logic.completeness_degree(profile["completeness_flags"])
    return {"fired_rules": rules, "objectives": sorted(set(goals)), "clarification_requests": clarification,
            "gap_analysis": {"matched_skills": matched, "missing_required_skills": missing,
                             "missing_preferred_skills": missing_preferred,
                             "skill_match_score": score, "skill_match_label": label,
                             "github_activity_score": activity_score, "github_activity_label": activity_label,
                             "profile_completeness_score": completeness, "profile_completeness_label": completeness_label,
                             "memberships": {"skill_match": fuzzy_logic.memberships(score, "skill"),
                                             "github_activity": fuzzy_logic.memberships(activity_score, "activity"),
                                             "source_coverage": fuzzy_logic.memberships(completeness, "completeness")},
                             "project_keyword_matches": project_matches, "relevant_certifications": relevant_certs},
            "visibility_assessment": {"selected_level": visibility_level,
                                      "public_contact_info_detected": public_contact, "findings": findings}}
