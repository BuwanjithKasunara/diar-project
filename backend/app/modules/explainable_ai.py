"""Rule-traced summaries describe observed evidence without rating the person."""


def build_explanation_summary(profile, benchmark_name, assessment, visibility_assessment, recommendations):
    evidence = assessment["benchmark_evidence"]
    sources = assessment["source_scope"]
    recency = assessment["github_portfolio_recency"]
    if recency["availability"] == "available":
        recency_text = (
            f"{recency['recently_pushed_owned_repository_count']} of "
            f"{recency['owned_public_non_fork_repository_count']} scanned owned public non-fork repositories "
            f"have a repository push timestamp within {recency['window_days']} days."
        )
    else:
        recency_text = "Owned-public-repository recency was not assessed."
    return {
        "narrative": (
            f"For the {benchmark_name} benchmark, supplied sources contain strong evidence for "
            f"{evidence['evidenced_count']} of {evidence['total_count']} capability groups. "
            f"{sources['usable_count']} of {sources['supported_total']} supported source types were usable. "
            f"{recency_text} These observations describe supplied public evidence, not overall competence or "
            "professional activity. " + " ".join(visibility_assessment["findings"])
        ),
        "top_recommendation_reasons": [r["explanation"] for r in recommendations[:3]],
        "recommendations_count": len(recommendations),
    }
