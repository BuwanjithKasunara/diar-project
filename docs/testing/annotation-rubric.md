# Independent concept and evidence-level review

This protocol labels a specific skill in a synthetic profile. The level is the **strength of evidence shown in the supplied profile**, not a verified measure of a person's ability. Use the same rubric for every role group. Record uncertainty rather than guessing.

## Concept mapping decisions

Review the claim text, sample contexts, candidate concept labels, categories, and definitions. Search the full ESCO/O*NET catalogue when the listed candidates do not fit. A shared name alone does not prove that two concepts are interchangeable.

- `single_match`: one catalogue concept has the intended meaning. Put exactly that ID in `concept_ids`.
- `multiple_valid`: two or more source concepts fit, and choosing one would lose a meaningful distinction. List all valid IDs. This decision does not assign a single canonical ID.
- `none`: no suitable catalogue concept was found after checking the catalogue. Leave `concept_ids` empty.
- `needs_context`: the claim or available context cannot disambiguate its meaning. Leave `concept_ids` empty.

The public mapping packet omits the pipeline's lexical status and frequency. They are retained only in the local internal manifest for coverage analysis. A reviewer may correct an exact lexical match or select a catalogue ID absent from the initial candidate list, provided the rationale explains the choice.

### Mapping specificity checks

- Read the concept definition and source category, not just the preferred label. A named product such as a particular analytics tool is not automatically synonymous with a broad concept such as "analytical software," even if the source lists that product as an example. Search for a product-specific concept first. If only a broader category exists, use `none` for this *canonical* concept decision and name the related category in the rationale; a separate typed relationship would be needed to preserve that broader link.
- Use `needs_context` when the claim has two or more plausible meanings and the supplied text cannot choose between them. Use `none` when the meaning is clear but the catalogue lacks a sufficiently specific concept. Do not use `needs_context` merely because a product-specific concept is absent.
- Use `multiple_valid` only when the supplied meaning independently supports every selected concept. A broad category and its narrower instance do not become two canonical matches simply because both are related.
- Treat a lexical match as a candidate, not a verdict. If its definition does not fit the claim in context, reject it and explain why.

These checks were clarified after the three-model synthetic pilot exposed repeated category-versus-product disagreements. The AI decisions remain provisional; a human reviewer should apply this clarified rubric to the disputed tasks rather than treating any model's choice as ground truth.

## Evidence-level decisions

Assess the target skill using only the evidence in that task. Select one label:

- `insufficient_evidence`: only a skill-list assertion, aspiration, title, tenure, vague claim, or unrelated evidence is available. This means **unknown**, not low ability.
- `foundational`: concrete introductory use is shown, such as a guided exercise, basic project task, or described application of core concepts. A degree title alone does not qualify.
- `applied`: concrete independent use is shown in a project or work product, including a specific contribution or result. Generic “worked with X” wording is too thin.
- `advanced`: evidence shows complex design, debugging, evaluation of trade-offs, improvement, or teaching of the target skill across meaningful work. A senior title, years of experience, or one unsupported superlative does not qualify.

For every positive label, cite at least one `evidence_id` from a professional evidence unit beyond `stated_skill`. The validator enforces this minimum; reviewers still need to judge whether the cited text truly supports the target. Explain the decision in `rationale`. If evidence conflicts or the task is unclear, choose `insufficient_evidence` and describe the conflict.

For `applied` versus `advanced`, look for complexity in the **target skill itself**. A senior title, team leadership, or a quantified result in the surrounding project does not raise a routine use of that skill to `advanced`. For `foundational` versus `applied`, distinguish assisted participation in an established process from clearly owned decisions or deliverables. If the text leaves that responsibility unclear, explain the uncertainty instead of inferring it from the job title.

Reviewers must not use synthetic `cohort`, `seniority`, `job_family`, `seed_role`, or `sample_group` as labels or clues. These fields are absent from public review packets. An evidence excerpt may contain a role title or duration; those alone do not determine a level. O*NET occupation `level` ratings describe an occupation requirement and never label a candidate.

## Independent review protocol

Two people review the same packet separately, without seeing each other's answers. Each uses a distinct stable reviewer ID and completes every task in their own JSON Lines file. The schema is [review-annotation-v1.schema.json](../../data/schema/review-annotation-v1.schema.json). Every answer retains its `task_id` and `task_digest`; the digest rejects answers to a changed packet.

For mapping, the two reviewers agree only when both decision and selected ID set match. For evidence level, they agree when both level labels match; both rationales remain in the resolved record. Disagreements go to a third reviewer, whose file contains only disagreement tasks. The third reviewer must have a different ID. `multiple_valid` and `needs_context` remain explicit outcomes even when reviewers agree.

Agreement is a quality check, not proof of correctness. The pilot covers synthetic text and must not be used as evidence of real-world model accuracy. Human identities and rationale files stay local with the annotation batch. If only one reviewer is available, the packet can be used for a provisional pilot, but it does not satisfy the independent-label gate.

## Local workflow

From the repository root, after the central-profile and concept-mapping builders have run:

```powershell
.venv-dev\Scripts\python.exe scripts\data\prepare_annotation_batches.py
.venv-dev\Scripts\python.exe scripts\data\create_review_templates.py --kind mapping --tasks data\annotation_batches\pilot_v1\mapping_tasks.jsonl --output-dir data\annotation_batches\pilot_v1\annotations
.venv-dev\Scripts\python.exe scripts\data\create_review_templates.py --kind level --tasks data\annotation_batches\pilot_v1\level_tasks.jsonl --output-dir data\annotation_batches\pilot_v1\annotations
```

The generator creates 125 mapping tasks and 50 level tasks by default. The level packet uses ten distinct profiles per sample group and balances tasks with and without a direct skill mention in professional text. The hidden internal manifests retain the group and source identifiers for later error analysis. Blank answer templates must be filled by the actual reviewers; empty responses fail validation. Do not regenerate packets after review begins. The generator refuses to overwrite existing packets unless `--replace` is explicitly supplied, and templates refuse to replace files with answers.

When both reviewers finish a packet, run its reconciliation command. For mapping:

```powershell
.venv-dev\Scripts\python.exe scripts\data\review_annotations.py --kind mapping --tasks data\annotation_batches\pilot_v1\mapping_tasks.jsonl --first data\annotation_batches\pilot_v1\annotations\mapping_reviewer-a.jsonl --second data\annotation_batches\pilot_v1\annotations\mapping_reviewer-b.jsonl --output-dir data\annotation_batches\pilot_v1\mapping_review
```

For levels, use `--kind level`, `level_tasks.jsonl`, the two `level_reviewer-*.jsonl` files, and a separate `level_review` output directory. If there are disagreements, give the `needs_adjudication.jsonl` queue to a third reviewer and run the same command with `--adjudication <third-reviewer-file> --replace`. `resolved.jsonl` retains the original answers and the final decision. The report records agreement and remaining disagreements; it does not create XGBoost training data.

### Pilot dispute and expanded synthetic packets

The pilot's AI disagreement queues are local under `data/annotation_batches/pilot_v1/ai_mapping_review/` and `ai_level_review/`. The `blind_adjudication_tasks.jsonl` files contain only the disputed tasks; they omit both AI answers. The blank `mapping_human-adjudicator.jsonl` and `level_human-adjudicator.jsonl` files in `pilot_v1/annotations/` are for a future human reviewer. That reviewer should use the clarified specificity checks above and fill their own stable `reviewer_id`. The three-model AI reconciliation under `ai_mapping_astra_review/` and `ai_level_astra_review/` is a workflow pilot and must stay separate from human review.

To regenerate a blind packet from a fresh disagreement queue, use `scripts/data/export_blind_adjudication.py` with `--kind`, `--queue`, `--tasks`, and `--output`. It verifies that every queued task is unchanged from the original packet and refuses to overwrite an existing blind packet. `create_review_templates.py --reviewer human-adjudicator` creates one blank response file from that blind packet; without `--reviewer`, it creates the two normal independent-review templates. Existing answers are protected from accidental replacement.

The 100-task expanded synthetic packet is prepared with:

```powershell
.venv-dev\Scripts\python.exe scripts\data\prepare_expanded_level_batch.py
.venv-dev\Scripts\python.exe scripts\data\create_review_templates.py --kind level --tasks data\annotation_batches\expanded_synthetic_v1\level_tasks.jsonl --output-dir data\annotation_batches\expanded_synthetic_v1\annotations
```

It excludes all 50 pilot profiles, selects 20 distinct profiles per design group, and balances direct and indirect skill mentions. Two humans should complete `level_reviewer-a.jsonl` and `level_reviewer-b.jsonl` independently. The packet contains synthetic profiles only; its design balance does not establish real-user representativeness. Do not train or evaluate XGBoost as a validated knowledge-level model until sufficient human labels from representative profiles and a profile-level held-out evaluation set exist.
