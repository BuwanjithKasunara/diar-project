"""Export disputed tasks without prior reviewers' answers for a third review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from map_central_claims import read_jsonl
from prepare_annotation_batches import write_jsonl
from review_annotations import load_tasks


def export_blind_queue(
    queue_path: Path, tasks_path: Path, output_path: Path, kind: str,
) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite blind review packet: {output_path}")
    source_tasks = load_tasks(tasks_path, kind)
    blind_tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in read_jsonl(queue_path):
        task = row.get("task")
        if not isinstance(task, dict) or task.get("kind") != kind:
            raise ValueError(f"invalid dispute task in {queue_path}")
        task_id = task.get("task_id")
        if task_id in seen or task_id not in source_tasks:
            raise ValueError(f"duplicate or unknown dispute task: {task_id}")
        if task != source_tasks[task_id]:
            raise ValueError(f"dispute task differs from original packet: {task_id}")
        if "first_annotation" not in row or "second_annotation" not in row:
            raise ValueError(f"missing reviewer decisions in dispute queue: {task_id}")
        blind_tasks.append(task)
        seen.add(task_id)
    if not blind_tasks:
        raise ValueError(f"no disputed tasks in {queue_path}")
    write_jsonl(output_path, blind_tasks, replace=False)
    return {"kind": kind, "tasks": len(blind_tasks), "output": str(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("mapping", "level"), required=True)
    args = parser.parse_args()
    result = export_blind_queue(
        args.queue.resolve(), args.tasks.resolve(), args.output.resolve(), args.kind,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
