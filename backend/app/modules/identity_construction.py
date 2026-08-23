"""
Identity Construction Module
-----------------------------
Consolidates the outputs of the Information Extraction Module
(resume, GitHub, LinkedIn) into a single, deduplicated, structured
Digital Identity Profile that downstream modules can reason over.
"""


def build_digital_identity_profile(resume: dict, github: dict, linkedin: dict) -> dict:
    all_skills = set()
    all_skills.update(resume.get("skills", []))
    all_skills.update(github.get("skills", []))
    all_skills.update(github.get("languages", []))
    all_skills.update(linkedin.get("skills", []))

    all_certifications = list({*resume.get("certifications", []), *linkedin.get("certifications", [])})
    all_education = list({*resume.get("education", []), *linkedin.get("education", [])})

    years_experience = resume.get("estimated_years_experience", 0)

    completeness_flags = {
        "resume_provided": resume.get("raw_text_length", 0) > 0,
        "github_provided": "error" not in github and bool(github.get("username")),
        "linkedin_provided": linkedin.get("profile_complete", False),
    }
    sources_provided = sum(1 for v in completeness_flags.values() if v)

    profile = {
        "skills": sorted(all_skills),
        "certifications": all_certifications,
        "education": all_education,
        "estimated_years_experience": years_experience,
        "github": {
            "username": github.get("username"),
            "repo_count": github.get("repo_count", 0),
            "recently_active_repo_count": github.get("recently_active_repo_count", 0),
            "languages": github.get("languages", []),
            "followers": github.get("followers", 0),
            "profile_complete": github.get("profile_complete", False),
            "top_repos": github.get("top_repos", []),
            "bio": github.get("bio"),
        },
        "linkedin": {
            "headline": linkedin.get("headline"),
            "profile_complete": linkedin.get("profile_complete", False),
        },
        "resume": {
            "provided": resume.get("raw_text_length", 0) > 0,
            "projects_snippet": resume.get("projects_snippet", ""),
            "experience_snippet": resume.get("experience_snippet", ""),
        },
        "completeness_flags": completeness_flags,
        "sources_provided_count": sources_provided,
        "public_contact_info_detected": _detect_contact_exposure(resume, linkedin),
    }
    return profile


def _detect_contact_exposure(resume: dict, linkedin: dict) -> bool:
    """Heuristic: resume text longer than a stub and containing an email
    or phone-like pattern is treated as exposing direct contact info,
    used later by the visibility/privacy rules."""
    import re
    text = (resume.get("experience_snippet", "") or "") + (linkedin.get("headline", "") or "")
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    phone_pattern = re.compile(r"(\+?\d[\d\-\s]{8,}\d)")
    return bool(email_pattern.search(text) or phone_pattern.search(text))
