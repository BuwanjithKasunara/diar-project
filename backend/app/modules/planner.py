"""Uniform-cost search over a bounded, versioned action catalogue."""
import heapq
import json
from pathlib import Path
from .. import config

CATALOGUE = json.loads((Path(__file__).parents[1] / "data/action_catalogue.json").read_text())


def candidates(objectives, role, visibility, skills):
    goals = set(objectives)
    actions = []
    templates = CATALOGUE["templates"]

    def add(id, title, kind, covers, prerequisites=()):
        template = templates[kind]
        explanation = ("Evidence-documentation action; it does not imply that an unobserved capability is absent."
                       if kind in ("profile", "document") else
                       "Hypothetical development action; relative effort is a catalogue assumption, not evidence of acquired competence.")
        actions.append({"id": id, "title": title, "cost": template["cost"],
                        "objectives": sorted(set(covers)), "prerequisites": sorted(prerequisites),
                        "roles": [role], "visibilities": template["visibilities"],
                        "explanation": explanation})

    for objective in sorted(goals):
        if objective.startswith("skill:"):
            skill = objective.split(":", 1)[1]
            add("learn:" + skill, "Develop and document " + skill, "learn", [objective])
        elif objective.startswith("capability:"):
            capability = objective.split(":", 1)[1]
            add("learn-capability:" + capability, "Develop and document " + capability.replace("-", " "),
                "learn", [objective])
    project = CATALOGUE["projects"][role]
    needed = [s for s in project["prerequisite_skills"] if s not in skills]
    for skill in needed:
        if not any(a["id"] == "learn:" + skill for a in actions):
            add("learn:" + skill, "Develop and document " + skill, "learn", ["skill:" + skill])
    sharing = {"Fully Public": "public", "Semi-Public": "selective-sharing", "Privacy Focused": "private"}[visibility]
    coverage = {"evidence:project", *["skill:" + s for s in project["skills"]]}
    if goals & coverage:
        add("project:" + role, project["title"] + f" ({sharing})", "project", coverage,
            ["learn:" + s for s in needed])
    if "privacy:contact" in goals:
        add("privacy:contact", "Replace public contact details with selective contact sharing", "privacy", ["privacy:contact"])
    if "evidence:profile" in goals:
        add("profile:sections", "Add relevant supporting profile sections", "profile", ["evidence:profile"])
    # A standalone portfolio action also allows plans where all prerequisite skills are already evidenced.
    if "evidence:project" in goals:
        add("portfolio:" + role, f"Document a relevant {sharing} portfolio", "project", ["evidence:project"])
    return actions


def search(actions, objectives, role, visibility, max_actions=None, max_states=None, fallback=None):
    max_actions = config.MAX_ACTIONS if max_actions is None else max_actions
    max_states = config.MAX_STATES if max_states is None else max_states
    goals = frozenset(objectives)
    eligible = sorted([a for a in actions if role in a["roles"] and visibility in a["visibilities"]],
                      key=lambda a: a["id"])
    ids = [a["id"] for a in eligible]
    if len(ids) != len(set(ids)) or any(not isinstance(a["cost"], int) or a["cost"] < 1 for a in eligible):
        raise ValueError("Catalogue needs unique IDs and positive integer costs.")
    expanded = 0

    def result(state, path, cost, status):
        covered = {g for a in eligible if a["id"] in state for g in a["objectives"]}
        lookup = {a["id"]: a for a in eligible}
        return {"status": status, "steps": [lookup[id] for id in path], "total_cost": cost,
                "objectives": sorted(goals), "unresolved_objectives": sorted(goals-covered),
                "expanded_states": expanded, "optimal": status in ("optimal", "no_actions_needed"),
                "fallback_recommendations": fallback or [] if status not in ("optimal", "no_actions_needed") else []}

    if not goals:
        return result(frozenset(), (), 0, "no_actions_needed")
    # Never silently truncate the catalogue then claim global optimality.
    if len(eligible) > max_actions:
        return result(frozenset(), (), 0, "candidate_limit")
    queue = [(0, (), frozenset())]
    best = {frozenset(): (0, ())}
    while queue:
        cost, path, chosen = heapq.heappop(queue)
        if best[chosen] != (cost, path):
            continue
        covered = {g for a in eligible if a["id"] in chosen for g in a["objectives"]}
        if goals <= covered:
            return result(chosen, path, cost, "optimal")
        if expanded >= max_states:
            return result(frozenset(), (), 0, "search_limit")
        expanded += 1
        for action in eligible:
            id = action["id"]
            if id in chosen or not set(action["prerequisites"]) <= chosen:
                continue
            next_state = chosen | {id}
            next_path, next_cost = path + (id,), cost + action["cost"]
            candidate = (next_cost, next_path)
            if next_state not in best or candidate < best[next_state]:
                best[next_state] = candidate
                heapq.heappush(queue, (next_cost, next_path, next_state))
    return result(frozenset(), (), 0, "unreachable")


def generate_plan(objectives, role, visibility, skills, recommendations):
    return search(candidates(objectives, role, visibility, set(skills)), objectives,
                  role, visibility, fallback=recommendations)

