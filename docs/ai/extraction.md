# Extraction

DIAR uses canonical concepts, aliases, regex/context checks, and restricted typo matching; no trained neural classifier is used. Version 3 adds concepts needed by the capability benchmarks, including LLMs, generative AI, neural networks, AI agents, RAG, model evaluation, vector databases, CUDA, JAX, LangChain, and LangGraph.

Evidence distinguishes claimed, planned, negated, uncertain, and explicit-gap language. Only supported positive claims contribute to capability evidence. Assertion matching uses word boundaries and technical-phrase safeguards, so a term such as `Q-learning` is not treated as a plan to learn. Ambiguous words still require technical or skill-list context, and complex prose can be misread.

Each evidence record retains a stable identifier, canonical concept, source, origin, normalized `artifact_type`, `repository_locator` when relevant, excerpt, `extraction_method`, assertion, and strength. Direct evidence strengths are:

- README: `1.0`.
- Résumé, LinkedIn, GitHub bio, or repository description: `0.8`.
- Repository name, topic, or whitelisted language metadata: `0.6`.
- Typo match: no more than `0.5`.
- Curated related-concept match: half the direct strength.

Duplicate mentions do not increase a capability beyond its strongest evidence. Only whitelisted GitHub languages become skill evidence; `Dockerfile` maps to Docker, while unknown languages remain repository metadata.

## GitHub collection

GitHub analysis covers owned public non-fork repositories. It reads the user profile, paginates repository metadata to the configured limit, and selects at most five non-archived repositories for README evidence: three ordered by benchmark relevance, stars, then recency, plus the two most-recent remaining repositories. Each README contributes at most 20,000 characters.

A scan makes no more than 11 requests: one profile request, up to five repository-page requests, and up to five README requests. A normal 404 for a repository without a README is skipped. Rate limits, malformed responses, truncation, and other incomplete fetches produce a `partial` source with a reason while preserving usable results. GitHub public events are not used for the 180-day observation; repository push timestamps supply factual recency counts instead.

This scope excludes organisation-owned repositories, private work, and contributions to repositories the person does not own. Names, topics, languages, descriptions, and README text are evidence of documented concepts, not verified proficiency or project quality.

Employment extraction uses relevant sections, excludes education dates, merges overlaps, and uses the supplied/as-of date for ongoing work. Ambiguous or absent experience remains unknown. PDFs must contain readable text; invalid, encrypted, textless, and oversized files receive clear reasons, and OCR is deferred.

See [data model](../architecture/data-model.md), [dataset guide](../testing/dataset-guide.md), and [privacy](../privacy/data-handling.md).

