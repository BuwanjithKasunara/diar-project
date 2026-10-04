# Contributor instructions

- Preserve the local Python/FastAPI, SQLite, vanilla JavaScript architecture unless an authorized change requires otherwise.
- Update requirements, API examples, algorithms, diagrams, privacy notes, and user instructions in the same change as implementation. Follow the [documentation workflow](docs/development/documentation-workflow.md).
- Record significant architecture, algorithm, persistence, privacy, and compatibility decisions as numbered ADRs. Preserve accepted history and supersede decisions explicitly.
- Independent documentation drafting may run in parallel after interfaces are agreed. The implementation owner verifies final documentation against code.
- Run relevant regression tests and the documentation checker. Record actual results and limitations, never invented success.
- Use isolated temporary databases. Do not modify saved user reports in tests.
- Use synthetic or redacted fixtures; never add credentials or personal profiles.
- Separate planned responsibilities from verified contribution evidence. Module responsibility does not establish authorship.

