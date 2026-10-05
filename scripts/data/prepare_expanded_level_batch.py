"""Prepare a disjoint synthetic level-review batch for future human annotation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from map_central_claims import read_jsonl
from prepare_annotation_batches import level_tasks, write_jsonl


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_expanded_batch(
    profiles_path: Path, excluded_manifest_path: Path, output_dir: Path,
    per_group: int = 20,
) -> dict[str, Any]:
    if per_group < 1:
        raise ValueError("per_group must be positive")
    paths = {
        "tasks": output_dir / "level_tasks.jsonl",
        "internal": output_dir / "level_internal_manifest.jsonl",
        "summary": output_dir / "batch_summary.json",
    }
    if any(path.exists() for path in paths.values()):
        raise FileExistsError(f"refusing to overwrite existing batch in {output_dir}")
    excluded_ids = {item["profile_id"] for item in read_jsonl(excluded_manifest_path)}
    if not excluded_ids:
        raise ValueError("the exclusion manifest contains no profile IDs")
    profiles = [
        profile for profile in read_jsonl(profiles_path)
        if profile["profile_id"] not in excluded_ids
    ]
    tasks, internal = level_tasks(profiles, per_group)
    if any(item["profile_id"] in excluded_ids for item in internal):
        raise ValueError("expanded batch overlaps the pilot profiles")
    if len({item["profile_id"] for item in internal}) != len(internal):
        raise ValueError("expanded batch reuses a profile")
    summary = {
        "annotation_version": "1.0.0",
        "source_type": "synthetic_design_sample",
        "representative_real_profiles": False,
        "human_labels_assigned": 0,
        "level_task_count": len(tasks),
        "per_group": dict(sorted(Counter(item["sample_group"] for item in internal).items())),
        "direct_text_match": dict(sorted(Counter(str(item["direct_text_match"]).lower() for item in internal).items())),
        "excluded_pilot_profile_count": len(excluded_ids),
        "source_sha256": file_sha256(profiles_path),
        "excluded_manifest_sha256": file_sha256(excluded_manifest_path),
    }
    write_jsonl(paths["tasks"], tasks, replace=False)
    write_jsonl(paths["internal"], internal, replace=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths["summary"].write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=root / "data/processed/central_profiles_mapped_v1.jsonl")
    parser.add_argument("--exclude-manifest", type=Path, default=root / "data/annotation_batches/pilot_v1/level_internal_manifest.jsonl")
    parser.add_argument("--output-dir", type=Path, default=root / "data/annotation_batches/expanded_synthetic_v1")
    parser.add_argument("--per-group", type=int, default=20)
    args = parser.parse_args()
    result = prepare_expanded_batch(
        args.profiles.resolve(), args.exclude_manifest.resolve(), args.output_dir.resolve(), args.per_group,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
