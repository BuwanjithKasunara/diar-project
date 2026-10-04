# 0010: Exact taxonomy concept mapping before semantic matching

Date: 2026-10-04  
Status: Accepted

## Context

Central profile claims need stable links to benchmark concepts. ESCO and O*NET overlap but do not provide a complete, one-to-one crosswalk, and the same surface label can identify multiple source concepts. Automatically merging concepts or fuzzily selecting one would introduce unreviewed meaning into the dataset.

## Decision

Build one catalogue containing source-preserved ESCO skill/knowledge concepts and O*NET essential-skill, knowledge, and software categories. ESCO concept URIs and O*NET Element IDs remain authoritative source identifiers; entries are not merged across taxonomies. O*NET workplace software examples and ESCO alternative labels are retained as aliases.

Map explicit profile claims only by case-insensitive, whitespace-normalized exact equality with a preferred label or alias. A label with one candidate receives that canonical concept ID. A label with multiple candidates is marked `ambiguous` and receives no canonical ID. A label with no candidate remains `unmapped`. No fuzzy, embedding, or transformer mapping is used in this stage.

## Alternatives

- Merge matching ESCO/O*NET labels into one concept: matching text does not prove semantic equivalence.
- Select the first matching concept: ordering is not a defensible disambiguation rule.
- Apply fuzzy matching immediately: likely to increase coverage while hiding mapping errors.
- Treat unmatched claims as absent knowledge: confuses taxonomy coverage with candidate capability.

## Consequences

Exact mappings are reproducible and auditable but coverage is intentionally limited. Ambiguous and unmatched claims stay visible for later labelled review or semantic-mapping experiments. Exact lexical mapping is not evidence of proficiency or concept equivalence. Occupation-specific benchmark weights remain a separate dataset-design step.

## Related documents

- [Concept catalogue schema](../../data/schema/concept-catalog-v1.schema.json)
- [Central profile schema](../../data/schema/central-profile-v1.schema.json)
- [Source mappings](../../data/schema/source-mappings-v1.json)
- [Dataset guide](../testing/dataset-guide.md)
