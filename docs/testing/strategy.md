# Test strategy

Use deterministic synthetic data, mocked network calls, and temporary databases.

- Extraction: assertions, aliases, typo restrictions, Q-learning wording, evidence strengths/provenance, employment dates, overlaps, and PDF failures.
- GitHub: README/topic evidence, empty descriptions, older flagship projects, deterministic selection, partial/rate-limited fetches, unknown languages, Dockerfile mapping, and the 11-request bound.
- Sources: missing/success/partial/failed, truncation, malformed results, and `not_assessed` when relevant evidence is unavailable.
- Alignment: all careers/visibility choices, any-of capabilities, strongest-evidence scoring, state thresholds, fuzzy method details, and source-scope separation.
- Planner: exhaustive minimum-cost comparison, prerequisites, combined actions, privacy, unreachable goals, limits.
- Recommendations/planner safety: no competence, certification, inactivity, or learning claim from absence alone; documentation actions for `not_observed`; learning only for explicit gaps.
- API/persistence: v3 analysis, v2/v3 saving, nullable history version, explicit deletion, deterministic results, and semantically unchanged v2/unversioned retrieval.
- Interface: evidence-scope warning, factual counts, provenance, collapsed method details, legacy warning/new-analysis action, keyboard use, narrow screens, history, and offline state.

Property/regression cases verify that duplicate keywords, followers, stale repositories, and repository ordering do not increase benchmark evidence; adding old repositories cannot lower an activity grade because version 3 has no such grade. TensorFlow or PyTorch can satisfy model tooling, while LLM evidence cannot invent Data systems or Delivery evidence.

Run `python -m pytest backend/tests -q`, `python scripts/check_docs.py`, and `python scripts/evaluate.py`. The documentation checker has its own tests: `python -m unittest discover -s scripts -p test_check_docs.py -v`. Record actual [results](results/development-verification.md); live GitHub smoke testing is optional and separate.

The version 3 evaluation gates are macro extraction precision `>= 0.90`, macro extraction recall `>= 0.85`, at least 90% of strong-evidence cases avoiding weak/limited outcomes, at least 95% of keyword-stuffed or trivial-repository cases avoiding broad evidence coverage, every insufficient-evidence case returning `not_assessed`, and zero absence-only cases producing confirmed-gap wording. A gate is a target until an actual evaluation run is recorded; documentation must not imply it passed merely because regression tests pass.

Passing regressions does not prove real-world accuracy, benchmark validity, usability, or suitability for shared hosting.

