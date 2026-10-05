"""Create editable, unlabelled reviewer response templates for a review packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from map_central_claims import read_jsonl
from prepare_annotation_batches import write_jsonl


def create_templates(
    tasks_path: Path, output_dir: Path, kind: str, refresh_unanswered: bool = False,
    reviewer_names: tuple[str, ...] | None = None,
) -> dict[str, int]:
    tasks = list(read_jsonl(tasks_path))
    if not tasks or any(task.get("kind") != kind for task in tasks):
        raise ValueError("task file is empty or contains a different review kind")
    names = reviewer_names or ("reviewer-a", "reviewer-b")
    if len(set(names)) != len(names) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in names):
        raise ValueError("reviewer names must be unique filename-safe identifiers")
    paths = [output_dir / f"{kind}_{name}.jsonl" for name in names]
    for path in paths:
        if not path.exists():
            continue
        if not refresh_unanswered:
            raise FileExistsError("reviewer template already exists; preserve existing human edits")
        existing = list(read_jsonl(path))
        if len(existing) != len(tasks) or any(
            item.get("rationale") or item.get("decision") or item.get("level") or item.get("concept_ids")
            or item.get("supporting_evidence_ids") for item in existing
        ):
            raise ValueError(f"refusing to replace a template with human edits: {path}")
    for name, path in zip(names, paths):
        rows = []
        for task in tasks:
            row = {
                "annotation_version": "1.0.0",
                "kind": kind,
                "task_id": task["task_id"],
                "task_digest": task["task_digest"],
                "reviewer_id": "",
                "rationale": "",
            }
            if kind == "mapping":
                row.update({"decision": "", "concept_ids": []})
            else:
                row.update({"level": "", "supporting_evidence_ids": []})
            rows.append(row)
        write_jsonl(path, rows, replace=refresh_unanswered)
    return {"tasks": len(tasks), "reviewer_files": len(paths)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--kind", choices=("mapping", "level"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reviewer", action="append", dest="reviewers", help="template filename suffix; repeat for multiple reviewers")
    parser.add_argument("--refresh-unanswered", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = create_templates(
        args.tasks.resolve(), args.output_dir.resolve(), args.kind, args.refresh_unanswered,
        tuple(args.reviewers) if args.reviewers else None,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
