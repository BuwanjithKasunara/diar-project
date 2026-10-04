"""Validate two independent review files and prepare agreement/adjudication outputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from map_central_claims import read_jsonl
from prepare_annotation_batches import stamp_digest, write_jsonl


def load_tasks(path: Path, kind: str) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for task in read_jsonl(path):
        if task.get("kind") != kind or task.get("annotation_version") != "1.0.0":
            raise ValueError(f"unexpected task kind or version in {path}")
        digest = task.get("task_digest")
        expected_digest = stamp_digest({key: value for key, value in task.items() if key != "task_digest"})["task_digest"]
        if digest != expected_digest:
            raise ValueError(f"task content changed without updating digest: {task.get('task_id')}")
        task_id = task["task_id"]
        if task_id in tasks:
            raise ValueError(f"duplicate task: {task_id}")
        tasks[task_id] = task
    if not tasks:
        raise ValueError(f"no tasks in {path}")
    return tasks


def validate_annotation(
    item: dict[str, Any], task: dict[str, Any], kind: str,
    validator: Draft202012Validator, catalog_ids: set[str],
) -> None:
    validator.validate(item)
    if item["kind"] != kind or item["task_id"] != task["task_id"]:
        raise ValueError(f"annotation does not match task {task['task_id']}")
    if item["task_digest"] != task["task_digest"]:
        raise ValueError(f"stale task digest for {task['task_id']}")
    if kind == "mapping":
        decision = item["decision"]
        concept_ids = item["concept_ids"]
        expected = 1 if decision == "single_match" else 2 if decision == "multiple_valid" else 0
        if len(concept_ids) < expected or (decision != "multiple_valid" and len(concept_ids) != expected):
            raise ValueError(f"invalid concept count for {task['task_id']}: {decision}")
        unknown = set(concept_ids) - catalog_ids
        if unknown:
            raise ValueError(f"unknown catalogue concepts for {task['task_id']}: {sorted(unknown)}")
    else:
        by_id = {evidence["evidence_id"]: evidence for evidence in task["evidence"]}
        unknown = set(item["supporting_evidence_ids"]) - by_id.keys()
        if unknown:
            raise ValueError(f"unknown evidence for {task['task_id']}: {sorted(unknown)}")
        if item["level"] != "insufficient_evidence":
            non_skill = [
                evidence_id for evidence_id in item["supporting_evidence_ids"]
                if by_id[evidence_id]["artifact_type"] != "stated_skill"
            ]
            if not non_skill:
                raise ValueError(f"positive level needs professional evidence for {task['task_id']}")


def load_annotations(
    path: Path, tasks: dict[str, dict[str, Any]], kind: str,
    validator: Draft202012Validator, catalog_ids: set[str],
    *, complete: bool,
) -> tuple[str, dict[str, dict[str, Any]]]:
    annotations: dict[str, dict[str, Any]] = {}
    reviewers: set[str] = set()
    for item in read_jsonl(path):
        task_id = item.get("task_id")
        if task_id not in tasks:
            raise ValueError(f"unknown task {task_id} in {path}")
        if task_id in annotations:
            raise ValueError(f"duplicate annotation for {task_id} in {path}")
        validate_annotation(item, tasks[task_id], kind, validator, catalog_ids)
        annotations[task_id] = item
        reviewers.add(item["reviewer_id"])
    if len(reviewers) != 1:
        raise ValueError(f"each file must contain exactly one reviewer: {path}")
    if complete and set(annotations) != set(tasks):
        raise ValueError(f"incomplete review file {path}: {len(annotations)}/{len(tasks)} tasks")
    return next(iter(reviewers)), annotations


def decision_key(item: dict[str, Any], kind: str) -> tuple[Any, ...]:
    return (
        (item["decision"], tuple(sorted(item["concept_ids"])))
        if kind == "mapping" else (item["level"],)
    )


def reconcile(
    kind: str, tasks_path: Path, first_path: Path, second_path: Path,
    output_dir: Path, schema_path: Path, catalog_path: Path | None = None,
    adjudication_path: Path | None = None, replace: bool = False,
) -> dict[str, Any]:
    output_paths = (
        output_dir / "resolved.jsonl",
        output_dir / "needs_adjudication.jsonl",
        output_dir / "review_report.json",
    )
    if not replace and any(path.exists() for path in output_paths):
        raise FileExistsError(f"review outputs already exist in {output_dir}; use --replace")
    tasks = load_tasks(tasks_path, kind)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validator.check_schema(schema)
    catalog_ids = (
        {item["concept_id"] for item in read_jsonl(catalog_path)}
        if kind == "mapping" and catalog_path else set()
    )
    if kind == "mapping" and not catalog_ids:
        raise ValueError("mapping review requires the concept catalogue")
    first_reviewer, first = load_annotations(
        first_path, tasks, kind, validator, catalog_ids, complete=True
    )
    second_reviewer, second = load_annotations(
        second_path, tasks, kind, validator, catalog_ids, complete=True
    )
    if first_reviewer == second_reviewer:
        raise ValueError("the two review files must have different reviewer IDs")

    disagreements = [task_id for task_id in tasks if decision_key(first[task_id], kind) != decision_key(second[task_id], kind)]
    adjudication: dict[str, dict[str, Any]] = {}
    if adjudication_path:
        reviewer, adjudication = load_annotations(
            adjudication_path,
            {task_id: tasks[task_id] for task_id in disagreements},
            kind, validator, catalog_ids, complete=True,
        )
        if reviewer in {first_reviewer, second_reviewer}:
            raise ValueError("adjudicator must differ from both initial reviewers")

    resolved: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    for task_id, task in tasks.items():
        if task_id in disagreements and task_id not in adjudication:
            pending.append({
                "task": task,
                "first_annotation": first[task_id],
                "second_annotation": second[task_id],
            })
            continue
        chosen = adjudication.get(task_id, first[task_id])
        status = chosen["decision"] if kind == "mapping" else chosen["level"]
        statuses[status] += 1
        resolved.append({
            "task_id": task_id,
            "annotation_version": "1.0.0",
            "kind": kind,
            "decision_source": "adjudication" if task_id in adjudication else "independent_agreement",
            "reviewer_ids": [first_reviewer, second_reviewer]
            + ([adjudication[task_id]["reviewer_id"]] if task_id in adjudication else []),
            "decision": chosen["decision"] if kind == "mapping" else chosen["level"],
            "concept_ids": chosen["concept_ids"] if kind == "mapping" else [],
            "supporting_evidence_ids": (
                chosen["supporting_evidence_ids"] if kind == "level" else []
            ),
            "rationale": chosen["rationale"],
            "source_annotations": [first[task_id], second[task_id]]
            + ([adjudication[task_id]] if task_id in adjudication else []),
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_paths[0], resolved, replace=replace)
    write_jsonl(output_paths[1], pending, replace=replace)
    report = {
        "annotation_version": "1.0.0",
        "kind": kind,
        "tasks": len(tasks),
        "reviewers": [first_reviewer, second_reviewer],
        "initial_agreements": len(tasks) - len(disagreements),
        "initial_disagreements": len(disagreements),
        "initial_agreement_rate": round((len(tasks) - len(disagreements)) / len(tasks), 6),
        "adjudicated": len(adjudication),
        "pending_adjudication": len(pending),
        "resolved_status_counts": dict(sorted(statuses.items())),
        "training_ready": False,
        "training_ready_reason": "This review only prepares vetted annotation records; no model dataset or split is built.",
    }
    report_temp = output_paths[2].with_suffix(".json.tmp")
    try:
        report_temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_temp.replace(output_paths[2])
    finally:
        report_temp.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("mapping", "level"), required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=root / "data/interim/concept_catalog_v1.jsonl")
    parser.add_argument("--schema", type=Path, default=root / "data/schema/review-annotation-v1.schema.json")
    parser.add_argument("--replace", action="store_true", help="replace generated reconciliation outputs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = reconcile(
        args.kind, args.tasks.resolve(), args.first.resolve(), args.second.resolve(),
        args.output_dir.resolve(), args.schema.resolve(), args.catalog.resolve(),
        args.adjudication.resolve() if args.adjudication else None,
        args.replace,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
