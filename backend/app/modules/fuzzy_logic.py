"""
Knowledge Representation Module (Fuzzy Logic)
-----------------------------------------------
Professional competence is rarely binary ("present"/"absent"). This
module represents profile characteristics -- skill match, GitHub
activity, and profile completeness -- as fuzzy degrees between 0 and 1
using triangular membership functions, then maps each degree onto a
linguistic label (low / moderate / strong) for use by the rule-based
expert system.

This is a lightweight, dependency-free fuzzy inference implementation
(equivalent in spirit to scikit-fuzzy's trimf/interp_membership), kept
self-contained so the prototype has no heavyweight numerical stack.
"""
from typing import Tuple


def _triangular(x: float, a: float, b: float, c: float) -> float:
    """Standard triangular membership function with foot points a, c and peak b."""
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


def skill_match_degree(user_skills: set, required_skills: set, preferred_skills: set) -> Tuple[float, str]:
    """Fuzzy degree of how strongly the user's skillset satisfies a
    benchmark, weighting required skills more heavily than preferred ones."""
    if not required_skills and not preferred_skills:
        return 1.0, "strong"

    required_hit = len(user_skills & required_skills) / max(1, len(required_skills))
    preferred_hit = len(user_skills & preferred_skills) / max(1, len(preferred_skills))
    score = 0.7 * required_hit + 0.3 * preferred_hit  # weighted crisp ratio, 0..1

    low = _triangular(score, -0.2, 0.0, 0.5)
    moderate = _triangular(score, 0.15, 0.5, 0.85)
    strong = _triangular(score, 0.5, 1.0, 1.2)

    label, _ = max([("low", low), ("moderate", moderate), ("strong", strong)], key=lambda t: t[1])
    return round(score, 3), label


def activity_degree(recently_active_repos: int, total_repos: int) -> Tuple[float, str]:
    """Fuzzy degree of GitHub activity level."""
    if total_repos == 0:
        return 0.0, "inactive"
    ratio = recently_active_repos / total_repos

    inactive = _triangular(ratio, -0.2, 0.0, 0.25)
    moderate = _triangular(ratio, 0.1, 0.4, 0.7)
    active = _triangular(ratio, 0.5, 1.0, 1.2)

    label, _ = max([("inactive", inactive), ("moderate", moderate), ("active", active)], key=lambda t: t[1])
    return round(ratio, 3), label


def completeness_degree(flags: dict) -> Tuple[float, str]:
    """Fuzzy degree of overall profile completeness across all sources."""
    provided = sum(1 for v in flags.values() if v)
    total = max(1, len(flags))
    ratio = provided / total

    incomplete = _triangular(ratio, -0.2, 0.0, 0.4)
    partial = _triangular(ratio, 0.2, 0.5, 0.8)
    complete = _triangular(ratio, 0.6, 1.0, 1.2)

    label, _ = max([("incomplete", incomplete), ("partial", partial), ("complete", complete)], key=lambda t: t[1])
    return round(ratio, 3), label
