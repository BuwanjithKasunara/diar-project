# Verification record

Date: 2026-09-27. Base revision: `f2ef9730d32b22d23ae9572503c3bb63f2956722`; improvement changes are an uncommitted working tree.

## Documentation checks executed

- `.venv-dev/Scripts/python.exe scripts/check_docs.py`: passed with 0 errors.
- `.venv-dev/Scripts/python.exe -m unittest discover -s scripts -p test_check_docs.py -v`: 3 tests passed. Temporary fixtures cover valid/encoded/external links, missing files, and duplicate ADR numbers.

The checker validates local target existence, not heading fragments, remote URLs, or factual correctness of prose.

## Application verification

Status: implementation and verification in progress. No application-test success or measured extraction improvement is asserted by this initial record.

After checks run, record command, date, code revision (or uncommitted working tree), fixture version, result, and limitations.

Required evidence includes backend/API/database checks, exhaustive planner comparisons, extraction baseline comparisons, documentation links, and browser/keyboard/narrow-screen checks. Unavailable checks remain outstanding.
