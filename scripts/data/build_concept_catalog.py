"""Build a versioned ESCO/O*NET concept catalogue without merging source IDs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


SCHEMA_VERSION = "1.0.0"


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def unique_text(values: Iterable[Any], preferred_label: str) -> list[str]:
    result: dict[str, str] = {}
    preferred_key = clean_text(preferred_label).casefold()
    for value in values:
        text = clean_text(value)
        key = text.casefold()
        if text and key != preferred_key:
            result.setdefault(key, text)
    return [result[key] for key in sorted(result)]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def esco_entries(path: Path) -> Iterable[dict[str, Any]]:
    concepts: dict[str, dict[str, str]] = {}
    semantic_fields = ("preferredLabel", "altLabels", "skillType", "description")
    for row in read_csv(path):
        uri = clean_text(row.get("conceptUri"))
        label = clean_text(row.get("preferredLabel"))
        if not uri or not label:
            continue
        if uri in concepts and any(row.get(field) != concepts[uri].get(field) for field in semantic_fields):
            raise ValueError(f"conflicting ESCO rows for {uri}")
        concepts.setdefault(uri, row)
    for uri, row in sorted(concepts.items()):
        label = clean_text(row.get("preferredLabel"))
        source_id = uri.rsplit("/", 1)[-1]
        alt_labels = str(row.get("altLabels") or "").splitlines()
        yield {
            "schema_version": SCHEMA_VERSION,
            "concept_id": f"esco:{source_id}",
            "source": "esco",
            "source_concept_id": uri,
            "category": "knowledge" if clean_text(row.get("skillType")) == "knowledge" else "skill",
            "preferred_label": label,
            "aliases": unique_text(alt_labels, label),
            "description": clean_text(row.get("description")) or None,
        }


def onet_entries(onet_dir: Path) -> Iterable[dict[str, Any]]:
    descriptions = {
        clean_text(row.get("Element ID")): clean_text(row.get("Description"))
        for row in read_csv(onet_dir / "content_model_reference.csv")
    }
    definitions = (
        ("essential_skills.csv", "skill"),
        ("knowledge.csv", "knowledge"),
    )
    for filename, category in definitions:
        concepts: dict[str, str] = {}
        for row in read_csv(onet_dir / filename):
            concepts.setdefault(clean_text(row.get("Element ID")), clean_text(row.get("Element Name")))
        for element_id, label in sorted(concepts.items()):
            if element_id and label:
                yield {
                    "schema_version": SCHEMA_VERSION,
                    "concept_id": f"onet:{element_id}",
                    "source": "onet",
                    "source_concept_id": element_id,
                    "category": category,
                    "preferred_label": label,
                    "aliases": [],
                    "description": descriptions.get(element_id) or None,
                }

    software: dict[str, dict[str, Any]] = defaultdict(lambda: {"label": "", "aliases": []})
    for row in read_csv(onet_dir / "software_skills.csv"):
        element_id = clean_text(row.get("Element ID"))
        if not element_id:
            continue
        software[element_id]["label"] = clean_text(row.get("Element Name"))
        software[element_id]["aliases"].append(row.get("Workplace Example"))
    for element_id, values in sorted(software.items()):
        label = values["label"]
        if label:
            yield {
                "schema_version": SCHEMA_VERSION,
                "concept_id": f"onet:{element_id}",
                "source": "onet",
                "source_concept_id": element_id,
                "category": "tool",
                "preferred_label": label,
                "aliases": unique_text(values["aliases"], label),
                "description": descriptions.get(element_id) or None,
            }


def build(esco_path: Path, onet_dir: Path, output_path: Path, schema_path: Path) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validator.check_schema(schema)
    esco_source_rows = len(read_csv(esco_path))
    esco = list(esco_entries(esco_path))
    entries = esco + list(onet_entries(onet_dir))
    concept_ids = [entry["concept_id"] for entry in entries]
    if len(concept_ids) != len(set(concept_ids)):
        raise ValueError("duplicate concept_id in catalogue")
    for entry in entries:
        validator.validate(entry)
    entries.sort(key=lambda entry: entry["concept_id"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            for entry in entries:
                stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        counts[f"{entry['source']}_{entry['category']}"] += 1
    return {
        "concepts": len(entries),
        "counts": dict(sorted(counts.items())),
        "esco_source_rows": esco_source_rows,
        "esco_duplicate_rows_collapsed": esco_source_rows - len(esco),
    }


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--esco", type=Path, default=root / "data/raw/esco/skills_en.csv")
    parser.add_argument("--onet", type=Path, default=root / "data/raw/onet")
    parser.add_argument("--output", type=Path, default=root / "data/interim/concept_catalog_v1.jsonl")
    parser.add_argument(
        "--schema", type=Path, default=root / "data/schema/concept-catalog-v1.schema.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build(args.esco.resolve(), args.onet.resolve(), args.output.resolve(), args.schema.resolve())
    print(json.dumps(summary, sort_keys=True))
    print(f"Wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
