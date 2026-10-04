# Recommendation planner

Priority ranking orders independent suggestions. Uniform-cost search explores combinations to satisfy objectives at minimum relative effort within a bounded catalogue.

Actions have stable IDs, positive costs, objectives, prerequisites, roles, and visibility compatibility. Small/medium/large costs are 1/2/3 relative units, not hours.

States track selected actions and addressed objectives. Required-skill development, relevant evidence improvements, and privacy conflicts form goals. Rule R11 adds `evidence:profile` when supplied LinkedIn text has sparse section coverage and the user selects Fully Public; the profile-section action costs 1. Clarification/source recovery remain separate. Suggested completion never changes current scores.

The [versioned catalogue](../../backend/app/data/action_catalogue.json) currently assigns learning cost 2, project/portfolio cost 3, and profile/privacy cost 1. Role-specific combined projects have explicit prerequisite skills. Already evidenced prerequisites need no learning step. Otherwise the generated prerequisite action must precede the project.

The frontier uses accumulated cost and deterministic tie-breaking. Prerequisites precede dependents; actions cannot repeat. Default limits are 20 candidates including prerequisites and 50,000 expansions.

Completed search establishes minimum cost only within its model. Limits/unreachable objectives return labelled fallback and unresolved objectives without an optimality claim. Verify against exhaustive small examples and baseline ranking.

The current limit fallback returns no proposed search steps and retains all goal objectives as unresolved, alongside independent ranked recommendations. It does not return a partial path or silently truncate the catalogue. Status values are `optimal`, `no_actions_needed`, `candidate_limit`, `search_limit`, and `unreachable`.

See [search ADR](../adr/0004-uniform-cost-planning.md) and [test strategy](../testing/strategy.md).
