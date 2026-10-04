# Dataset guide

Development dataset version 1 contains [30 synthetic profiles](../../backend/tests/fixtures/profiles.json): two per career/visibility combination, using skills-only and public-contact variants. Labels identify skills, source states, required/forbidden rules, and sharing-compatible actions. [Six focused cases](../../backend/tests/fixtures/baseline.json) retain extraction outputs from revision `f2ef9730d32b22d23ae9572503c3bb63f2956722`.

Version 3 adds [the evidence-scoring evaluation set](../../backend/tests/fixtures/evaluation_v3.json) and [deterministic GitHub REST snapshots](../../backend/tests/fixtures/github_v3.json), each marked `dataset_version: 3.0`. All identities and repository content are synthetic or anonymised. The evaluation set covers natural-language expert-like evidence, novices, sparse profiles, archive-heavy accounts, keyword stuffing, trivial fresh repositories, unavailable sources, and expected capability states. The GitHub snapshots cover README/topic extraction, empty descriptions, older relevant repositories, pagination/selection, rate limits, missing READMEs, unknown languages, and Dockerfile mapping.

Run `python scripts/evaluate.py` to print the legacy regression metrics and version 3 gate metrics as JSON without writing files. Version 3 reports macro extraction precision/recall, strong-evidence retention, keyword-stuffing/trivial-repository resistance, insufficient-evidence handling, and absence-only recommendation safety. Baseline comparison applies only to the six focused cases; the 30-profile matrix has current labels/results but no captured historical baseline. Empty denominators produce null metrics. Never use private personal data in fixtures.

These authored regression cases cannot establish general accuracy. Final evaluation needs independently labelled held-out examples and annotation guidance. See [results](results/development-verification.md) for actual fixture provenance and measurements.

