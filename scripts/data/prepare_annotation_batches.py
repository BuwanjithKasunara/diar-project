"""Prepare blind mapping and evidence-level review packets from central profiles.

Generated packets are local artifacts. No annotation or proficiency label is inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from map_central_claims import normalize, read_jsonl


VERSION = "1.0.0"
GROUPS = (
    "software_engineering", "data_science", "research", "product",
    "entrepreneurial_adjacent",
)


def stable_id(kind: str, *parts: str) -> str:
    value = "\x1f".join((VERSION, kind, *parts))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def stamp_digest(task: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**task, "task_digest": hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]}


def contains_label(text: str, label: str) -> bool:
    if len(label) < 3:
        return False
    return bool(re.search(r"(?<!\w)" + re.escape(label) + r"(?!\w)", text, re.I))


def mapping_tasks(
    profiles: list[dict[str, Any]], catalog: dict[str, dict[str, Any]],
    limits: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    labels: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        units = profile["profile_evidence"]["evidence_units"]
        context = [unit for unit in units if unit["artifact_type"] != "stated_skill"]
        for claim in profile["profile_evidence"]["claims"]:
            label = normalize(claim["normalized_text"])
            status = claim["mapping_status"]
            candidates = tuple(claim["mapping_candidates"])
            entry = labels.setdefault(label, {
                "status": status, "candidates": candidates, "instances": 0, "contexts": [],
            })
            if (entry["status"], entry["candidates"]) != (status, candidates):
                raise ValueError(f"inconsistent lexical mapping for {label}")
            entry["instances"] += 1
            if len(entry["contexts"]) < 2:
                for unit in context:
                    excerpt = unit["text"][:600]
                    if contains_label(excerpt, label) and excerpt not in entry["contexts"]:
                        entry["contexts"].append(excerpt)
                        break

    selected = []
    internal = []
    for status in ("ambiguous", "unmapped", "exact"):
        ranked = sorted(
            ((label, entry) for label, entry in labels.items() if entry["status"] == status),
            key=lambda item: (-item[1]["instances"], item[0]),
        )
        for label, entry in ranked[:limits[status]]:
            candidates = []
            for concept_id in entry["candidates"]:
                concept = catalog.get(concept_id)
                if concept is None:
                    raise ValueError(f"missing catalogue concept: {concept_id}")
                candidates.append({
                    "concept_id": concept_id,
                    "preferred_label": concept["preferred_label"],
                    "category": concept["category"],
                    "description": concept["description"],
                })
            task_id = "map-" + stable_id("mapping", label)
            selected.append(stamp_digest({
                "annotation_version": VERSION,
                "kind": "mapping",
                "task_id": task_id,
                "claim_text": label,
                "candidate_concepts": candidates,
                "sample_contexts": entry["contexts"],
            }))
            internal.append({
                "task_id": task_id,
                "lexical_status": status,
                "claim_instances": entry["instances"],
            })
    return selected, internal


def level_tasks(
    profiles: list[dict[str, Any]], per_group: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: dict[str, dict[bool, list[tuple[str, dict[str, Any], dict[str, Any], list[dict[str, Any]]]]]] = {
        group: {True: [], False: []} for group in GROUPS
    }
    for profile in profiles:
        group = profile["design_labels"]["sample_group"]
        if group not in candidates:
            raise ValueError(f"unexpected design group: {group}")
        units = profile["profile_evidence"]["evidence_units"]
        non_skill = [unit for unit in units if unit["artifact_type"] != "stated_skill"]
        by_id = {unit["evidence_id"]: unit for unit in units}
        for claim in profile["profile_evidence"]["claims"]:
            label = normalize(claim["normalized_text"])
            stated = [by_id[evidence_id] for evidence_id in claim["evidence_ids"]]
            direct = any(contains_label(unit["text"], label) for unit in non_skill)
            # All available professional evidence is shown so a reviewer can assess context.
            evidence = stated + non_skill
            candidates[group][direct].append((
                stable_id("level-order", profile["profile_id"], label), profile, claim, evidence
            ))

    tasks: list[dict[str, Any]] = []
    internal: list[dict[str, Any]] = []
    for group in GROUPS:
        chosen = []
        used_profiles: set[str] = set()
        quotas = ((True, per_group // 2), (False, per_group - per_group // 2))
        for direct, quota in quotas:
            if quota == 0:
                continue
            for candidate in sorted(candidates[group][direct], key=lambda item: item[0]):
                profile_id = candidate[1]["profile_id"]
                if profile_id not in used_profiles:
                    chosen.append((direct, candidate))
                    used_profiles.add(profile_id)
                if sum(item[0] == direct for item in chosen) >= quota:
                    break
        if len(chosen) < per_group:
            remaining = sorted(candidates[group][True] + candidates[group][False], key=lambda item: item[0])
            for candidate in remaining:
                profile_id = candidate[1]["profile_id"]
                if profile_id not in used_profiles:
                    direct = any(contains_label(unit["text"], candidate[2]["normalized_text"])
                                 for unit in candidate[3] if unit["artifact_type"] != "stated_skill")
                    chosen.append((direct, candidate))
                    used_profiles.add(profile_id)
                if len(chosen) == per_group:
                    break
        if len(chosen) != per_group:
            raise ValueError(f"not enough distinct profiles in group {group}")
        for direct, (_, profile, claim, evidence) in chosen:
            task_id = "lvl-" + stable_id("level", profile["profile_id"], claim["normalized_text"])
            tasks.append(stamp_digest({
                "annotation_version": VERSION,
                "kind": "level",
                "task_id": task_id,
                "target_skill": claim["concept_text"],
                "evidence": [
                    {
                        "evidence_id": unit["evidence_id"],
                        "artifact_type": unit["artifact_type"],
                        "text": unit["text"],
                    }
                    for unit in evidence
                ],
            }))
            internal.append({
                "task_id": task_id,
                "profile_id": profile["profile_id"],
                "claim_id": claim["claim_id"],
                "sample_group": group,
                "direct_text_match": direct,
                "lexical_mapping_status": claim["mapping_status"],
            })
    return tasks, internal


def write_jsonl(path: Path, rows: list[dict[str, Any]], replace: bool) -> None:
    if path.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite {path}; use --replace for generated packets")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(
    profiles_path: Path, catalog_path: Path, output_dir: Path,
    limits: dict[str, int], per_group: int, replace: bool = False,
) -> dict[str, Any]:
    if per_group < 1 or any(value < 0 for value in limits.values()):
        raise ValueError("review limits must be non-negative and per-group must be positive")
    paths = {
        "mapping": output_dir / "mapping_tasks.jsonl",
        "mapping_internal": output_dir / "mapping_internal_manifest.jsonl",
        "level": output_dir / "level_tasks.jsonl",
        "internal": output_dir / "level_internal_manifest.jsonl",
        "summary": output_dir / "batch_summary.json",
    }
    if not replace:
        for path in paths.values():
            if path.exists():
                raise FileExistsError(f"refusing to overwrite {path}; use --replace for generated packets")
    profiles = list(read_jsonl(profiles_path))
    catalog = {item["concept_id"]: item for item in read_jsonl(catalog_path)}
    mapping, mapping_internal = mapping_tasks(profiles, catalog, limits)
    levels, internal = level_tasks(profiles, per_group)
    if len({task["task_id"] for task in mapping}) != len(mapping):
        raise ValueError("duplicate mapping task ID")
    if len({task["task_id"] for task in levels}) != len(levels):
        raise ValueError("duplicate level task ID")
    summary = {
        "annotation_version": VERSION,
        "mapping_task_counts": dict(Counter(item["lexical_status"] for item in mapping_internal)),
        "level_task_count": len(levels),
        "level_tasks_per_group": dict(Counter(item["sample_group"] for item in internal)),
        "direct_text_match_counts": dict(Counter(str(item["direct_text_match"]).lower() for item in internal)),
        "labels_assigned": 0,
    }
    write_jsonl(paths["mapping"], mapping, replace)
    write_jsonl(paths["mapping_internal"], mapping_internal, replace)
    write_jsonl(paths["level"], levels, replace)
    write_jsonl(paths["internal"], internal, replace)
    summary_temp = paths["summary"].with_suffix(".json.tmp")
    try:
        summary_temp.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary_temp.replace(paths["summary"])
    finally:
        summary_temp.unlink(missing_ok=True)
    return summary


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=root / "data/processed/central_profiles_mapped_v1.jsonl")
    parser.add_argument("--catalog", type=Path, default=root / "data/interim/concept_catalog_v1.jsonl")
    parser.add_argument("--output-dir", type=Path, default=root / "data/annotation_batches/pilot_v1")
    parser.add_argument("--ambiguous", type=int, default=50)
    parser.add_argument("--unmapped", type=int, default=50)
    parser.add_argument("--exact-audit", type=int, default=25)
    parser.add_argument("--per-group", type=int, default=10)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = prepare(
        args.profiles.resolve(), args.catalog.resolve(), args.output_dir.resolve(),
        {"ambiguous": args.ambiguous, "unmapped": args.unmapped, "exact": args.exact_audit},
        args.per_group, args.replace,
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"Wrote review packets to {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
