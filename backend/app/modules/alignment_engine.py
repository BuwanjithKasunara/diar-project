"""Evidence-aware rules. Unobserved evidence is never treated as proven inability."""
import re
from . import fuzzy_logic

VISIBILITY_LEVELS = ["Fully Public", "Semi-Public", "Privacy Focused"]
SUPPORTED_SOURCES = ("resume", "github", "linkedin")


def _flat_capabilities(benchmark):
    capabilities = []
    required = benchmark.get("required_skills", [])
    preferred = benchmark.get("preferred_skills", [])
    for importance, skills, total_weight in (("required", required, 0.7),
                                              ("preferred", preferred, 0.3)):
        if not skills:
            continue
        weight = total_weight / len(skills)
        capabilities.extend({"id": skill.replace(" ", "-"), "label": skill,
                             "weight": weight, "importance": importance, "skills": [skill]}
                            for skill in skills)
    if not capabilities:
        return [{"id": "general", "label": "General evidence", "weight": 1.0,
                 "importance": "preferred", "skills": []}]
    normalizer = sum(c["weight"] for c in capabilities)
    for capability in capabilities:
        capability["weight"] /= normalizer
    return capabilities


def benchmark_capabilities(benchmark):
    capabilities = benchmark.get("capabilities") or _flat_capabilities(benchmark)
    total = sum(float(c["weight"]) for c in capabilities)
    if not capabilities or abs(total - 1.0) > 1e-6:
        raise ValueError("Benchmark capability weights must sum to 1.")
    return capabilities


def _capability_result(capability, evidence, usable_sources):
    accepted = set(capability.get("skills", []))
    related = set(capability.get("related_skills", []))
    positive = [e for e in evidence if e.get("assertion") == "claimed" and e.get("skill") in accepted]
    related_positive = [e for e in evidence if e.get("assertion") == "claimed" and e.get("skill") in related]
    negative = [e for e in evidence if e.get("assertion") == "negated" and e.get("skill") in accepted]
    direct_strength = max((float(e.get("strength", 0.8)) for e in positive), default=0.0)
    related_strength = max((float(e.get("strength", 0.8)) * 0.5 for e in related_positive), default=0.0)
    strength = round(max(direct_strength, related_strength), 3)
    supporting = positive + related_positive
    if not usable_sources:
        state = "not_assessed"
    elif strength >= 0.6:
        state = "evidenced"
    elif strength > 0:
        state = "weakly_evidenced"
    elif negative:
        state = "explicit_gap"
    else:
        state = "not_observed"
    return {
        "id": capability["id"], "label": capability["label"],
        "importance": capability.get("importance", "preferred"),
        "weight": round(float(capability["weight"]), 4),
        "accepted_skills": sorted(accepted),
        "matched_skills": sorted({e["skill"] for e in supporting}),
        "evidence_ids": sorted({e.get("id") for e in supporting if e.get("id")}),
        "strength": strength, "state": state,
    }


def _source_scope(statuses):
    groups = {"usable": [], "partial": [], "failed": [], "not_supplied": []}
    for source in SUPPORTED_SOURCES:
        value = statuses.get(source, {}).get("status", "not_supplied")
        if value in ("analysed", "partial"):
            groups["usable"].append(source)
        if value == "partial":
            groups["partial"].append(source)
        elif value == "failed":
            groups["failed"].append(source)
        elif value == "not_supplied":
            groups["not_supplied"].append(source)
    return {"supported_total": len(SUPPORTED_SOURCES), "usable_count": len(groups["usable"]), **groups}


def _github_recency(profile):
    github = profile.get("github", {})
    count = github.get("repo_count")
    recent = github.get("recently_pushed_owned_repo_count")
    return {
        "availability": "available" if count is not None and recent is not None else "not_assessed",
        "window_days": github.get("activity_window_days") or 180,
        "owned_public_non_fork_repository_count": count,
        "recently_pushed_owned_repository_count": recent,
        "last_owned_repository_push_at": github.get("last_owned_repository_push_at"),
        "limitation": ("Repository push timestamps describe the scanned owned public repositories, not the "
                       "person's commits, contribution quality, organisation work, private work, or professional activity."),
    }


def run_alignment(profile, benchmark, benchmark_name, visibility_level):
    rules, clarification, goals = [], [], []
    statuses = profile["source_statuses"]
    source_scope = _source_scope(statuses)
    results = [_capability_result(c, profile["evidence"], source_scope["usable"])
               for c in benchmark_capabilities(benchmark)]
    score = None if not source_scope["usable"] else round(sum(r["weight"] * r["strength"] for r in results), 3)
    evidence_summary = {
        "score": score,
        "evidenced_count": sum(r["state"] == "evidenced" for r in results),
        "weakly_evidenced_count": sum(r["state"] == "weakly_evidenced" for r in results),
        "total_count": len(results),
        "capability_results": results,
        "memberships": fuzzy_logic.evidence_memberships(score),
        "method": "Weighted maximum positive evidence per benchmark capability; duplicate mentions do not accumulate.",
        "limitation": ("This is coverage of evidence found in supplied sources, not a probability or rating of "
                       "competence, seniority, reputation, or employability."),
    }

    def rule(id, action, title, priority, reason, objective=None):
        rules.append({"id": id, "action": action, "title": title, "priority": priority,
                      "condition": reason, "reason": reason, "objective": objective})
        if objective:
            goals.append(objective)

    explicit_gaps = [r for r in results if r["state"] == "explicit_gap"]
    for capability in explicit_gaps:
        rule("R1-explicit-" + capability["id"], "recommend_learning:" + capability["label"],
             "Develop " + capability["label"], "high",
             f"The supplied text explicitly negates experience in the {capability['label']} capability. "
             "This recommendation follows that self-description, not an absent keyword.",
             "capability:" + capability["id"])

    unobserved = [r for r in results if r["state"] in ("not_observed", "weakly_evidenced")]
    if unobserved:
        labels = ", ".join(r["label"] for r in unobserved)
        rule("R1-evidence", "recommend_profile", "Supply or document additional capability evidence", "medium",
             f"The analysed sources did not provide strong evidence for: {labels}. This does not establish a skill gap.",
             "evidence:profile")

    years = profile["estimated_years_experience"]
    if years is None and benchmark.get("min_experience_years", 0):
        clarification.append("Supply clearly dated employment history to assess experience.")
    elif years is not None and years < benchmark.get("min_experience_years", 0):
        rule("R3-experience", "recommend_gaining_experience", "Gain relevant experience", "medium",
             f"Parsed employment periods suggest about {years} years; the benchmark expects "
             f"{benchmark['min_experience_years']}.")

    repo = profile["github"]
    if benchmark.get("github_required", True) and statuses.get("github", {}).get("status") in ("failed", "partial"):
        clarification.append("Some GitHub portfolio evidence was unavailable; retry or supply another source if needed.")
    project_text = " ".join(p["excerpt"] for p in profile["project_evidence"]).lower()
    project_matches = sorted({kw for kw in benchmark.get("expected_project_keywords", [])
                              if re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", project_text)})
    if not project_matches and source_scope["usable"]:
        sharing = {"Fully Public": "publicly", "Semi-Public": "for selective sharing",
                   "Privacy Focused": "privately"}[visibility_level]
        rule("R4-project-evidence", "recommend_portfolio",
             "Supply or document relevant project evidence", "medium",
             f"No benchmark-relevant project description was observed. If such work exists, document it {sharing}; "
             "the absence of a detected description is not proof that no project exists.", "evidence:project")

    if not profile["completeness_flags"]["linkedin_provided"]:
        clarification.append("LinkedIn text was not analysed; it is optional and can supply additional evidence.")
    elif not profile["content_completeness"]["linkedin"] and visibility_level == "Fully Public":
        rule("R11-profile", "recommend_profile", "Add supporting sections to your professional profile", "medium",
             "The supplied LinkedIn text has limited section coverage. Add evidence only if it reflects your work.",
             "evidence:profile")

    public_contact = profile["public_contact_info_detected"]
    findings = []
    if public_contact and visibility_level != "Fully Public":
        rule("R10-privacy-contact", "recommend_privacy", "Reduce public contact exposure", "high",
             f"Contact information was detected in a source identified as public, conflicting with the "
             f"{visibility_level} preference.", "privacy:contact")
        findings.append("Contact details detected in a public source; consider selective contact sharing.")
    if any(c["visibility"] == "unverified" for c in profile["contact_findings"]):
        findings.append("Contact details occur in text with unverified visibility; public exposure is not established.")
    if any(c["visibility"] == "private" for c in profile["contact_findings"]):
        findings.append("Contact details in private input are not treated as public exposure.")
    findings.append({"Fully Public": "Public showcase actions are permitted.",
                     "Semi-Public": "Suggested actions favour selective sharing.",
                     "Privacy Focused": "Suggested actions support private portfolios."}[visibility_level])

    comparison = {
        "benchmark_identity": benchmark_name,
        "benchmark_description": benchmark["description"],
        "evidenced_capabilities": [r["label"] for r in results if r["state"] == "evidenced"],
        "weakly_evidenced_capabilities": [r["label"] for r in results if r["state"] == "weakly_evidenced"],
        "capabilities_not_observed": [r["label"] for r in results if r["state"] == "not_observed"],
        "explicit_gaps": [r["label"] for r in explicit_gaps],
        "project_keyword_matches": project_matches,
    }
    return {
        "fired_rules": rules, "objectives": sorted(set(goals)),
        "clarification_requests": list(dict.fromkeys(clarification)),
        "assessment": {"benchmark_evidence": evidence_summary, "source_scope": source_scope,
                       "github_portfolio_recency": _github_recency(profile)},
        "benchmark_comparison": comparison,
        "project_keyword_matches": project_matches,
        "visibility_assessment": {"selected_level": visibility_level,
                                  "public_contact_info_detected": public_contact, "findings": findings},
    }
