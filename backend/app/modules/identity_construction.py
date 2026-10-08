"""
Identity Construction Module
-----------------------------
Consolidates the outputs of the Information Extraction Module
(resume, GitHub, LinkedIn) into a single, deduplicated, structured
Digital Identity Profile with explicit source state tracking and
contextual skill categorization.
"""
from typing import Dict, Any, Set
from collections import Counter
import math


def build_digital_identity_profile(resume: dict, github: dict, linkedin: dict) -> dict:
    # 1. Context-Aware Skills Aggregation
    r_ctx = resume.get("contextual_skills", {})
    g_ctx = github.get("contextual_skills", {})
    l_ctx = linkedin.get("contextual_skills", {})

    claimed_skills = set(r_ctx.get("claimed", [])) | set(g_ctx.get("claimed", [])) | set(l_ctx.get("claimed", []))
    # Also add GitHub primary languages to claimed skills
    claimed_skills.update(github.get("languages", []))

    uncertain_skills = set(r_ctx.get("uncertain", [])) | set(g_ctx.get("uncertain", [])) | set(l_ctx.get("uncertain", []))
    # Remove any uncertain skills that are claimed in another source
    uncertain_skills -= claimed_skills

    planned_skills = set(r_ctx.get("planned", [])) | set(g_ctx.get("planned", [])) | set(l_ctx.get("planned", []))
    # Remove any planned skills that are actually claimed
    planned_skills -= (claimed_skills | uncertain_skills)

    negated_skills = set(r_ctx.get("negated", [])) | set(g_ctx.get("negated", [])) | set(l_ctx.get("negated", []))
    # A skill is only negated if it was never claimed or uncertain in another source
    negated_skills -= (claimed_skills | uncertain_skills | planned_skills)

    # Active skills pool used for standard matching
    active_skills = claimed_skills | uncertain_skills

    # Aggregate frequencies and normalized weights
    skill_frequencies = Counter()
    for ctx in (r_ctx, g_ctx, l_ctx):
        for s, count in ctx.get("frequency", {}).items():
            skill_frequencies[s] += count

    normalized_weights = {}
    for s, count in skill_frequencies.items():
        capped = min(count, 5)
        normalized_weights[s] = round(1.0 + (math.log(capped) * 0.4), 3) if capped > 1 else 1.0

    all_certifications = list({*resume.get("certifications", []), *linkedin.get("certifications", [])})
    all_education = list({*resume.get("education", []), *linkedin.get("education", [])})

    years_experience = resume.get("estimated_years_experience", 0)

    # 2. Explicit Data Source State Tracking
    r_state = resume.get("source_state", "not_supplied" if resume.get("raw_text_length", 0) == 0 else "analysed")
    g_state = github.get("source_state", "failed" if github.get("error") else ("not_supplied" if not github.get("username") else "analysed"))
    l_state = linkedin.get("source_state", "not_supplied" if linkedin.get("raw_text_length", 0) == 0 else "analysed")

    source_states = {
        "resume": r_state,
        "github": g_state,
        "linkedin": l_state,
    }

    completeness_flags = {
        "resume_provided": r_state == "analysed",
        "github_provided": g_state == "analysed",
        "linkedin_provided": l_state == "analysed",
    }

    valid_sources_count = sum(1 for s in source_states.values() if s == "analysed")
    has_insufficient_evidence = valid_sources_count == 0

    profile = {
        "skills": sorted(active_skills),
        "contextual_skills": {
            "claimed": sorted(claimed_skills),
            "uncertain": sorted(uncertain_skills),
            "planned": sorted(planned_skills),
            "negated": sorted(negated_skills),
            "frequencies": dict(skill_frequencies),
            "normalized_weights": normalized_weights,
        },
        "certifications": all_certifications,
        "education": all_education,
        "estimated_years_experience": years_experience,
        "source_states": source_states,
        "insufficient_evidence": has_insufficient_evidence,
        "github": {
            "username": github.get("username"),
            "state": g_state,
            "repository_state": github.get("repository_state", g_state),
            "repository_coverage": github.get("repository_coverage"),
            "repositories_fetched_count": github.get("repositories_fetched_count", 0),
            "error": github.get("error"),
            "repo_count": github.get("repo_count", 0),
            "recently_active_repo_count": github.get("recently_active_repo_count", 0),
            "moderate_repo_count": github.get("moderate_repo_count", 0),
            "stale_repo_count": github.get("stale_repo_count", 0),
            "languages": github.get("languages", []),
            "followers": github.get("followers", 0),
            "profile_complete": github.get("profile_complete", False),
            "top_repos": github.get("top_repos", []),
            "bio": github.get("bio"),
        },
        "linkedin": {
            "state": l_state,
            "headline": linkedin.get("headline"),
            "profile_complete": linkedin.get("profile_complete", False),
        },
        "resume": {
            "state": r_state,
            "provided": r_state == "analysed",
            "projects_snippet": resume.get("projects_snippet", ""),
            "experience_snippet": resume.get("experience_snippet", ""),
        },
        "completeness_flags": completeness_flags,
        "sources_provided_count": valid_sources_count,
        # Compatibility fallback for callers without source-aware evidence.
        # The analysis API overwrites this with provenance-aware findings.
        "public_contact_info_detected": _detect_contact_exposure(resume, linkedin),
    }
    return profile


def _detect_contact_exposure(resume: dict, linkedin: dict) -> bool:
    """Deprecated compatibility fallback; API analysis derives this from provenance-aware evidence."""
    import re
    text = (resume.get("experience_snippet", "") or "") + (linkedin.get("headline", "") or "")
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    phone_pattern = re.compile(r"(\+?\d[\d\-\s]{8,}\d)")
    return bool(email_pattern.search(text) or phone_pattern.search(text))
