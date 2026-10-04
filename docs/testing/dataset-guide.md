# Dataset guide

Development dataset version 1 contains [30 synthetic profiles](../../backend/tests/fixtures/profiles.json): two per career/visibility combination, using skills-only and public-contact variants. Labels identify skills, source states, required/forbidden rules, and sharing-compatible actions. [Six focused cases](../../backend/tests/fixtures/baseline.json) retain extraction outputs from revision `f2ef9730d32b22d23ae9572503c3bb63f2956722`.

Run `python scripts/evaluate.py` to print micro-averaged precision/recall, exact-match rates, counts, and errors as JSON without writing files. Baseline comparison applies only to the six focused cases; the 30-profile matrix has current labels/results but no captured historical baseline. Empty denominators produce null metrics. Never use private personal data in fixtures.

These authored regression cases cannot establish general accuracy. Final evaluation needs independently labelled held-out examples and annotation guidance. See [results](results/development-verification.md) for actual fixture provenance and measurements.
