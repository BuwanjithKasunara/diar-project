# Recommendation planner

Priority ranking orders independent suggestions. Uniform-cost search explores combinations to satisfy objectives at minimum relative effort within a bounded catalogue.

Actions have stable IDs, positive costs, objectives, prerequisites, roles, and visibility compatibility. Small/medium/large costs are 1/2/3 relative units, not hours.

States track selected actions and addressed objectives. Version 3 keeps evidence availability separate from development need:

- `not_assessed` creates a clarification/source-recovery request.
- `not_observed` can create one grouped documentation objective, never a learning objective.
- `explicit_gap` can create a skill-development objective.
- Verified experience below the benchmark can create an experience-development objective.

Relevant evidence improvements and privacy conflicts can also form goals. Project actions say to supply or document relevant project evidence and respect the selected visibility. Repository count, push ratio, language diversity, and unmatched certification no longer create planner goals. Suggested completion never changes current evidence scores.

The [versioned catalogue](../../backend/app/data/action_catalogue.json) currently assigns learning cost 2, project/documentation cost 3, and profile/privacy cost 1. Role-specific combined projects have explicit prerequisites. A learning prerequisite can only be introduced for an explicit gap; absence-only observations use documentation actions instead.

The frontier uses accumulated cost and deterministic tie-breaking. Prerequisites precede dependents; actions cannot repeat. Default limits are 20 candidates including prerequisites and 50,000 expansions.

Completed search establishes minimum cost only within its model. Limits/unreachable objectives return labelled fallback and unresolved objectives without an optimality claim. Verify against exhaustive small examples and baseline ranking.

The current limit fallback returns no proposed search steps and retains all goal objectives as unresolved, alongside independent ranked recommendations. It does not return a partial path or silently truncate the catalogue. Status values are `optimal`, `no_actions_needed`, `candidate_limit`, `search_limit`, and `unreachable`.

See [search ADR](../adr/0004-uniform-cost-planning.md) and [test strategy](../testing/strategy.md).

