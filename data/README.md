# DIAR dataset workspace

Downloaded datasets belong in `data/raw/<source>/`. Raw files are immutable inputs and are ignored by Git. Do not place a Python environment or application dependencies below `data/raw`; the audit command ignores an existing `.venv`, but it is not part of any dataset.

Current inputs:

- `esco/`: ESCO occupations, skills, and relations.
- `onet/`: O*NET occupation and capability tables.
- `skillspan/`: SkillSpan train, development, and test annotations.
- `synthetic_profiles/`: the original synthetic candidate profiles and the privacy-filtered design sample.

Upstream locations, locally observed versions, and intended uses are recorded in [`sources-manifest.csv`](sources-manifest.csv). A "downloaded snapshot" version is intentionally incomplete provenance: record an upstream release or commit before using that source in a reproducible training run.

Run the read-only inventory and contract checks from the repository root:

```powershell
.venv-dev\Scripts\python.exe scripts\data\audit_raw_data.py --output data\reports\raw-dataset-profile.json
```

The report contains row counts, column names, byte sizes, and SHA-256 checksums. Generated reports are local artifacts and are ignored by Git because checksums and sizes change whenever a source download changes.

Do not concatenate these inputs. ESCO and O*NET are taxonomies, SkillSpan is span-annotation data, and the synthetic profiles are design examples; treating their rows as interchangeable would create misleading labels. Their approved roles and mapping states are recorded in [`schema/source-mappings-v1.json`](schema/source-mappings-v1.json).

The versioned candidate contract is [`schema/central-profile-v1.schema.json`](schema/central-profile-v1.schema.json). Build the local normalized design profiles with:

```powershell
.venv-dev\Scripts\python.exe scripts\data\build_central_profiles.py
```

This writes `data/interim/central_profiles_v1.jsonl`. The builder makes no semantic inference: only explicit structured skills become claims, while professional free text is retained as provenance-bearing evidence. Generation labels are isolated from model input. The next gate is validation of canonical ESCO/O*NET concept mappings; independently labelled knowledge-level outcomes are still required before XGBoost experiments.

Build the source-preserving concept catalogue and apply conservative exact mappings with:

```powershell
.venv-dev\Scripts\python.exe scripts\data\build_concept_catalog.py
.venv-dev\Scripts\python.exe scripts\data\map_central_claims.py
```

The catalogue follows [`schema/concept-catalog-v1.schema.json`](schema/concept-catalog-v1.schema.json). Mapped profiles are written under `data/processed/`, and the coverage report is written under `data/reports/`; both are reproducible local artifacts. Exact mapping keeps ESCO and O*NET IDs separate, never chooses among ambiguous matches, and never treats unmatched claims as absent knowledge.

Build source-preserved occupation baselines with:

```powershell
.venv-dev\Scripts\python.exe scripts\data\build_occupation_benchmarks.py
```

The output follows [`schema/occupation-benchmark-v1.schema.json`](schema/occupation-benchmark-v1.schema.json). ESCO essential/optional relations and O*NET raw rating scales remain distinct; the builder does not invent a common weight. This completes the deterministic dataset-design pipeline. Human-reviewed concept mappings and independently labelled knowledge-level outcomes are the remaining gates before XGBoost experimentation.

The [annotation rubric](../docs/testing/annotation-rubric.md) describes the next local review stage. Run `scripts/data/prepare_annotation_batches.py` to create blind mapping and evidence-level packets under `data/annotation_batches/pilot_v1/`. The packet builder assigns no labels. Use `scripts/data/create_review_templates.py` for two blank reviewer files per task type, then `scripts/data/review_annotations.py` to validate completed independent reviews and prepare disagreement queues. All packets, reviewer answers, and internal manifests are ignored by Git.
