# 0007: Capability evidence scoring and factual GitHub observations

Date: 2026-10-04  
Status: Accepted

## Context

The version 2 report compared literal skill sets and presented winning labels such as `low` or `inactive`. GitHub extraction relied mainly on profile and repository metadata, while the activity ratio divided recently pushed repositories by every owned non-fork repository. These outputs could be mistaken for judgments of professional competence or activity even though they described only the supplied evidence and penalised established accounts with old repositories.

The redesign must remain deterministic, local-first, explainable, bounded against GitHub rate limits, and compatible with saved version 2 and unversioned report JSON.

## Decision

Use report schema and benchmark version 3.

- `assessment.benchmark_evidence` reports a weighted evidence score, capability results/counts, fuzzy memberships for method inspection, and an explicit limitation. A capability is satisfied by its strongest supporting evidence, not by duplicate mentions. The public result does not choose a `low`, `moderate`, or `strong` competence label.
- Capability states are `evidenced`, `weakly_evidenced`, `not_observed`, `not_assessed`, and `explicit_gap`. Missing text is not an explicit gap. Only explicit gaps or verified short experience can create development recommendations; absence-only results can request additional documentation.
- `assessment.source_scope` reports usable, partial, failed, and unsupplied sources as factual counts and lists. It is not a profile-quality or competence score.
- `assessment.github_portfolio_recency` reports availability, the observation window, owned public non-fork repository counts, recently pushed counts, and the latest repository push timestamp. It does not classify a person as active or inactive.
- GitHub evidence includes profile bio, repository names/descriptions/topics/languages, and up to five selected READMEs. Selection uses three non-archived repositories ordered by benchmark relevance, stars, and recency, then two most-recent remaining repositories. Each README is truncated to 20,000 characters. A scan uses at most one profile call, five repository-page calls, and five README calls; incomplete fetches return partial status and a reason.
- Every match keeps a stable evidence identifier, source/origin artifact, repository locator where applicable, excerpt, extraction method, assertion, and evidence strength. Initial direct-evidence strengths are README `1.0`; résumé, LinkedIn, GitHub bio, and repository description `0.8`; and repository name, topic, or whitelisted language metadata `0.6`. Typo evidence is capped at `0.5`; curated related-concept evidence receives a `0.5` multiplier.
- Only whitelisted GitHub languages become skill evidence. `Dockerfile` maps to Docker; unknown languages remain descriptive metadata.
- The GitHub REST public-events endpoint is not used for the 180-day observation because it exposes a shorter public-event window. Organisation-owned, private, and third-party contribution activity remains outside the claim.
- `POST /api/analyze` emits version 3 only. `POST /api/reports` temporarily accepts version 2 or version 3. Saved version 2 and unversioned JSON is neither migrated nor recalculated; readers and the interface render it as a historical heuristic report. Report-history rows expose a nullable schema version.

## Alternatives

- Tune the existing label thresholds or add exceptions for prominent accounts. This preserves the misleading construct and produces person-specific behaviour.
- Use public events, followers, stars, or reputation as expertise/activity scores. These signals are incomplete, popularity-sensitive, and do not cover the required observation window.
- Use an external language model to infer competence. This reduces determinism and local privacy and introduces cost and calibration requirements that are outside this phase.
- Rewrite all stored reports into version 3. That would invent evidence that was never collected and violate preservation of accepted report history.

## Consequences

Reports make narrower, auditable claims and expose the evidence behind each capability. README enrichment improves recall but costs additional requests and still samples only owned public repositories. Weighted capability evidence is a benchmark-specific observation, not a hiring decision or measurement of overall expertise.

The API and interface need explicit version branches. Legacy grades remain viewable only with a historical warning. Evaluation must cover evidence precision/recall, source failures, keyword stuffing, repository-order invariance, and absence-only recommendation safety.

## Related documents

- [Extraction](../ai/extraction.md)
- [Benchmarks and rules](../ai/benchmarks-and-rules.md)
- [Data model](../architecture/data-model.md)
- [API usage](../api/README.md)
- [Test strategy](../testing/strategy.md)
