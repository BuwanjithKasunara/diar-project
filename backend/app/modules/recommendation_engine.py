"""
Recommendation Engine (Search Algorithm)
-------------------------------------------
Takes the rules fired by the Digital Identity Alignment Engine and
produces an ordered, de-duplicated action plan. This is implemented as
a best-first priority search over the rule action space: each fired
rule is a candidate action with a priority weight and a benchmark-
relevance weight; actions are pushed onto a max-priority queue and
popped in order to build the final ranked recommendation list.
"""
import heapq

PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}

ACTION_LABELS = {
    "recommend_learning": "Develop skill: {arg}",
    "accelerate_learning": "Prioritise learning skill: {arg}",
    "structured_training": "Complete structured training in: {arg}",
    "continue_learning": "Continue learning skill: {arg}",
    "recommend_gaining_experience": "Gain additional relevant experience",
    "recommend_building_portfolio_projects": "Build additional portfolio projects on GitHub",
    "recommend_increasing_github_activity": "Increase GitHub activity / commit frequency",
    "recommend_diversifying_projects": "Diversify projects across more programming languages",
    "recommend_diversifying_selected_projects": "Build technical breadth and choose which projects to showcase",
    "recommend_diversifying_private_projects": "Build technical breadth privately; public sharing is optional",
    "recommend_certification": "Pursue a relevant professional certification",
    "recommend_adding_github": "Add and populate a GitHub profile",
    "provide_github_profile": "Provide a valid GitHub profile for analysis",
    "retry_github_analysis": "Retry GitHub analysis when repository data is available",
    "recommend_refreshing_github_repos": "Refresh older GitHub repositories with relevant updates",
    "recommend_refreshing_repos": "Refresh older GitHub repositories with relevant updates",
    "recommend_completing_linkedin": "Complete and expand LinkedIn profile content",
    "recommend_reducing_public_contact_exposure": "Reduce publicly exposed personal contact information",
    "recommend_maximising_profile_completeness": "Maximise profile completeness across all platforms",
    "provide_linkedin_for_analysis": "Paste LinkedIn text if you want it included in the analysis",
    "skip_linkedin_analysis": "Skip LinkedIn analysis or share its text only if comfortable",
    "skip_github_analysis": "Skip GitHub analysis or provide its public username only if comfortable",
    "recommend_private_portfolio_projects": "Develop portfolio projects privately and share selected evidence when useful",
    "recommend_curating_portfolio": "Develop portfolio work and choose which projects to showcase publicly",
    "recommend_refreshing_selected_repos": "Keep selected public repositories current; other projects can stay private",
    "recommend_refreshing_private_repos": "Keep relevant portfolio work current; public activity is optional",
    "review_public_exposure": "Review exposed {kind} in {source}",
}

EXPOSURE_LABELS = {
    "github_profile": "GitHub profile",
    "github_repository": "GitHub repository metadata",
    "github_repository_file": "public GitHub repository files",
    "linkedin": "LinkedIn text you supplied",
    "resume": "resume you marked publicly shared",
}
EXPOSURE_KIND_LABELS = {
    "email": "email address", "phone": "phone number",
    "street_address": "street address", "date_of_birth": "date of birth",
}


def _label_for(action: str) -> str:
    key, separator, arg = action.partition(":")
    template = ACTION_LABELS.get(key)
    if template is not None:
        if key == "review_public_exposure":
            source, _, kind = arg.partition(":")
            return template.format(
                source=EXPOSURE_LABELS.get(source, "the supplied source"),
                kind=EXPOSURE_KIND_LABELS.get(kind, "personal detail"),
            )
        return template.format(arg=arg)

    # Keep future actions readable, including their skill or other argument.
    label = key.replace("_", " ").capitalize()
    return f"{label}: {arg}" if separator else label


def generate_recommendations(fired_rules: list) -> list:
    """Best-first search: rank rule-derived actions by priority weight,
    breaking ties by insertion order (rule-list order reflects the
    order the expert system evaluated them in)."""
    heap = []
    for idx, rule in enumerate(fired_rules):
        weight = PRIORITY_WEIGHT.get(rule.get("priority", "low"), 1)
        # heapq is a min-heap; negate weight for max-priority behaviour
        heapq.heappush(heap, (-weight, idx, rule))

    ranked = []
    seen_actions = set()
    rank = 1
    while heap:
        neg_weight, idx, rule = heapq.heappop(heap)
        action = rule["action"]
        if action in seen_actions:
            continue
        seen_actions.add(action)
        ranked.append({
            "rank": rank,
            "priority": rule.get("priority"),
            "recommendation": _label_for(action),
            "rule_id": rule.get("id"),
            "explanation": rule.get("reason"),
            "category": rule.get("category", "career"),
            **{key: rule[key] for key in ("category", "source", "evidence_ids", "suggested_steps") if key in rule},
        })
        rank += 1

    return ranked
