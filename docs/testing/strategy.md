# Test strategy

Use deterministic synthetic data, mocked network calls, and temporary databases.

- Extraction: assertions, aliases, typo restrictions, employment dates, overlaps, PDF failures.
- Sources: missing/success/partial/failed, short text, pagination, rate limits, malformed results.
- Alignment: all careers/visibility choices, relevant projects/certifications, unknown assessments, fuzzy boundaries/empty groups.
- Planner: exhaustive minimum-cost comparison, prerequisites, combined actions, privacy, unreachable goals, limits.
- API/persistence: validation, explicit saving/deletion, deterministic results, legacy retrieval.
- Interface: warnings, nulls, previous results, keyboard, narrow screens, history, offline state.

Run `python -m pytest backend/tests -q`, `python scripts/check_docs.py`, and `python scripts/evaluate.py`. The documentation checker has its own tests: `python -m unittest discover -s scripts -p test_check_docs.py -v`. Record actual [results](results/development-verification.md); live GitHub smoke testing is optional and separate.

Passing regressions does not prove real-world accuracy, benchmark validity, usability, or suitability for shared hosting.
