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
    "recommend_gaining_experience": "Gain additional relevant experience",
    "recommend_building_portfolio_projects": "Build additional portfolio projects on GitHub",
    "recommend_increasing_github_activity": "Increase GitHub activity / commit frequency",
    "recommend_diversifying_projects": "Diversify projects across more programming languages",
    "recommend_certification": "Pursue a relevant professional certification",
    "recommend_adding_github": "Add and populate a GitHub profile",
    "recommend_completing_linkedin": "Complete and expand LinkedIn profile content",
    "recommend_reducing_public_contact_exposure": "Reduce publicly exposed personal contact information",
    "recommend_maximising_profile_completeness": "Maximise profile completeness across all platforms",
}


def _label_for(action: str) -> str:
    if ":" in action:
        key, arg = action.split(":", 1)
        template = ACTION_LABELS.get(key, key)
        return template.format(arg=arg)
    return ACTION_LABELS.get(action, action)


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
        })
        rank += 1

    return ranked
