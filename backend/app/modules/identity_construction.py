"""Consolidation preserves evidence and separates source availability from completeness."""
def build_digital_identity_profile(resume, github, linkedin):
    sources = {"resume": resume, "github": github, "linkedin": linkedin}
    statuses = {name: data.get("source_status", {"status": "not_supplied", "reason": None})
                for name, data in sources.items()}
    flags = {name + "_provided": statuses[name]["status"] in ("analysed", "partial") for name in sources}
    evidence = sorted([e for d in sources.values() for e in d.get("evidence", [])],
                      key=lambda e: (e["skill"], e["source"], e.get("origin", ""),
                                     e.get("repository") or "", e["excerpt"], e["method"], e["assertion"]))
    years = [d["estimated_years_experience"] for d in (resume, linkedin)
             if d.get("estimated_years_experience") is not None]
    contacts = [{"source": name, "visibility": d.get("visibility", "unverified"),
                 "detected": True} for name, d in sources.items() if d.get("contact_info_detected")]
    return {
        "skills": sorted({e["skill"] for e in evidence if e["assertion"] == "claimed"}),
        "evidence": evidence, "source_statuses": statuses,
        "certifications": sorted({c for d in sources.values() for c in d.get("certifications", [])}),
        "education": sorted({c for d in sources.values() for c in d.get("education", [])}),
        "estimated_years_experience": max(years) if years else None,
        "github": {k: github.get(k) for k in ("username", "repo_count", "recently_active_repo_count",
                   "recently_pushed_owned_repo_count", "last_owned_repository_push_at", "languages", "followers",
                   "profile_complete", "top_repos", "bio", "activity_window_days", "activity_proxy")},
        "linkedin": {"headline": linkedin.get("headline"), "profile_complete": linkedin.get("profile_complete", False)},
        "resume": {"provided": flags["resume_provided"], "projects_snippet": resume.get("projects_snippet", ""),
                   "experience_snippet": resume.get("experience_snippet", "")},
        "project_evidence": [{"source": name, "excerpt": d["projects_snippet"][:10000]}
                             for name, d in sources.items() if d.get("projects_snippet")],
        "completeness_flags": flags,
        "content_completeness": {name: d.get("profile_complete", False) for name, d in sources.items()},
        "sources_provided_count": sum(flags.values()),
        "contact_findings": contacts,
        "public_contact_info_detected": any(c["visibility"] == "public" for c in contacts),
    }
