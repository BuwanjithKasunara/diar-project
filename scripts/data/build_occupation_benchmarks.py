"""Build source-preserved ESCO and O*NET occupation benchmarks."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from build_concept_catalog import clean_text


SCHEMA_VERSION = "1.0.0"


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def iter_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def unique_source_rows(
    path: Path, id_field: str, semantic_fields: tuple[str, ...], source_name: str
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in iter_csv(path):
        identifier = clean_text(row.get(id_field))
        if not identifier:
            continue
        if identifier in result and any(
            row.get(field) != result[identifier].get(field) for field in semantic_fields
        ):
            raise ValueError(f"conflicting {source_name} rows for {identifier}")
        result.setdefault(identifier, row)
    return result


def numeric(value: Any) -> float | None:
    text = clean_text(value)
    try:
        return float(text) if text else None
    except ValueError as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc


def empty_requirement(concept_id: str, category: str, relationship: str) -> dict[str, Any]:
    return {
        "concept_id": concept_id,
        "category": category,
        "relationship": relationship,
        "importance": None,
        "level": None,
        "not_relevant": None,
        "suppressed": False,
        "examples": [],
        "hot_technology": None,
        "in_demand": None,
    }


def validate_benchmark(benchmark: dict[str, Any], categories: dict[str, str]) -> None:
    expected = {
        "schema_version", "benchmark_id", "source", "source_occupation_id",
        "title", "description", "requirements",
    }
    if set(benchmark) != expected or benchmark["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"invalid benchmark envelope: {benchmark.get('benchmark_id')}")
    if benchmark["source"] not in {"esco", "onet"} or not benchmark["title"]:
        raise ValueError(f"invalid benchmark identity: {benchmark.get('benchmark_id')}")
    seen: set[str] = set()
    for requirement in benchmark["requirements"]:
        concept_id = requirement["concept_id"]
        if concept_id in seen:
            raise ValueError(f"duplicate requirement {concept_id} in {benchmark['benchmark_id']}")
        seen.add(concept_id)
        if categories.get(concept_id) != requirement["category"]:
            raise ValueError(f"unknown or mismatched concept {concept_id}")
        if requirement["relationship"] not in {"essential", "optional", "rated", "software"}:
            raise ValueError(f"invalid relationship for {concept_id}")
        for field in ("importance", "level"):
            value = requirement[field]
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                raise ValueError(f"invalid {field} for {concept_id}")
        if requirement["suppressed"] and (
            requirement["importance"] is not None or requirement["level"] is not None
        ):
            raise ValueError(f"suppressed requirement retains ratings: {concept_id}")


def esco_benchmarks(esco_dir: Path, categories: dict[str, str]) -> Iterable[dict[str, Any]]:
    occupations = unique_source_rows(
        esco_dir / "occupations_en.csv",
        "conceptUri",
        ("preferredLabel", "description", "iscoGroup"),
        "ESCO occupation",
    )
    grouped: dict[str, dict[str, str]] = defaultdict(dict)
    for row in iter_csv(esco_dir / "occupationSkillRelations_en.csv"):
        occupation_uri = clean_text(row.get("occupationUri"))
        skill_uri = clean_text(row.get("skillUri"))
        concept_id = "esco:" + skill_uri.rsplit("/", 1)[-1]
        relationship = clean_text(row.get("relationType"))
        if concept_id not in categories:
            raise ValueError(f"ESCO relation references unknown concept: {concept_id}")
        existing = grouped[occupation_uri].get(concept_id)
        if existing and existing != relationship:
            grouped[occupation_uri][concept_id] = (
                "essential" if "essential" in {existing, relationship} else relationship
            )
            continue
        grouped[occupation_uri][concept_id] = relationship

    for uri, row in sorted(occupations.items()):
        occupation_id = uri.rsplit("/", 1)[-1]
        yield {
            "schema_version": SCHEMA_VERSION,
            "benchmark_id": f"esco:{occupation_id}",
            "source": "esco",
            "source_occupation_id": uri,
            "title": clean_text(row.get("preferredLabel")),
            "description": clean_text(row.get("description")) or None,
            "requirements": [
                empty_requirement(concept_id, categories[concept_id], relationship)
                for concept_id, relationship in sorted(grouped[uri].items())
            ],
        }


def onet_benchmarks(onet_dir: Path, categories: dict[str, str]) -> Iterable[dict[str, Any]]:
    occupations = unique_source_rows(
        onet_dir / "occupation_data.csv",
        "O*NET-SOC Code",
        ("Title", "Description"),
        "O*NET occupation",
    )
    requirements: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for filename in ("essential_skills.csv", "knowledge.csv"):
        ratings: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"suppressed": False, "importance": None, "level": None, "not_relevant": None}
        )
        for row in iter_csv(onet_dir / filename):
            key = (clean_text(row.get("O*NET-SOC Code")), clean_text(row.get("Element ID")))
            value = ratings[key]
            value["suppressed"] = value["suppressed"] or clean_text(row.get("Recommend Suppress")) == "Y"
            scale = clean_text(row.get("Scale ID"))
            if scale == "IM":
                value["importance"] = numeric(row.get("Data Value"))
            elif scale == "LV":
                value["level"] = numeric(row.get("Data Value"))
                flag = clean_text(row.get("Not Relevant"))
                value["not_relevant"] = True if flag == "Y" else False if flag == "N" else None
        for (occupation_id, element_id), rating in ratings.items():
            concept_id = f"onet:{element_id}"
            if concept_id not in categories:
                raise ValueError(f"O*NET rating references unknown concept: {concept_id}")
            requirement = empty_requirement(concept_id, categories[concept_id], "rated")
            requirement.update({
                "importance": None if rating["suppressed"] else rating["importance"],
                "level": None if rating["suppressed"] else rating["level"],
                "not_relevant": rating["not_relevant"],
                "suppressed": rating["suppressed"],
            })
            requirements[occupation_id][concept_id] = requirement

    software: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"examples": {}, "hot_technology": False, "in_demand": False}
    )
    for row in iter_csv(onet_dir / "software_skills.csv"):
        key = (clean_text(row.get("O*NET-SOC Code")), clean_text(row.get("Element ID")))
        value = software[key]
        example = clean_text(row.get("Workplace Example"))
        if example:
            value["examples"].setdefault(example.casefold(), example)
        value["hot_technology"] = value["hot_technology"] or clean_text(row.get("Hot Technology")) == "Y"
        value["in_demand"] = value["in_demand"] or clean_text(row.get("In Demand")) == "Y"
    for (occupation_id, element_id), values in software.items():
        concept_id = f"onet:{element_id}"
        if concept_id not in categories:
            raise ValueError(f"O*NET software relation references unknown concept: {concept_id}")
        requirement = empty_requirement(concept_id, categories[concept_id], "software")
        requirement.update({
            "examples": [values["examples"][key] for key in sorted(values["examples"])],
            "hot_technology": values["hot_technology"],
            "in_demand": values["in_demand"],
        })
        requirements[occupation_id][concept_id] = requirement

    for occupation_id, row in sorted(occupations.items()):
        yield {
            "schema_version": SCHEMA_VERSION,
            "benchmark_id": f"onet:{occupation_id}",
            "source": "onet",
            "source_occupation_id": occupation_id,
            "title": clean_text(row.get("Title")),
            "description": clean_text(row.get("Description")) or None,
            "requirements": sorted(
                requirements[occupation_id].values(), key=lambda item: item["concept_id"]
            ),
        }


def build(
    esco_dir: Path,
    onet_dir: Path,
    catalog_path: Path,
    output_path: Path,
    schema_path: Path,
) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validator.check_schema(schema)
    categories = {entry["concept_id"]: entry["category"] for entry in read_jsonl(catalog_path)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    benchmark_ids: set[str] = set()
    source_counts: dict[str, int] = defaultdict(int)
    requirement_counts: dict[str, int] = defaultdict(int)
    suppressed = 0
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            for source_benchmarks in (
                esco_benchmarks(esco_dir, categories),
                onet_benchmarks(onet_dir, categories),
            ):
                for benchmark in source_benchmarks:
                    if benchmark["benchmark_id"] in benchmark_ids:
                        raise ValueError(f"duplicate benchmark_id: {benchmark['benchmark_id']}")
                    benchmark_ids.add(benchmark["benchmark_id"])
                    validate_benchmark(benchmark, categories)
                    stream.write(json.dumps(benchmark, ensure_ascii=False, sort_keys=True) + "\n")
                    source = benchmark["source"]
                    source_counts[source] += 1
                    requirement_counts[source] += len(benchmark["requirements"])
                    suppressed += sum(item["suppressed"] for item in benchmark["requirements"])
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {
        "benchmarks": len(benchmark_ids),
        "benchmark_counts": dict(sorted(source_counts.items())),
        "requirement_counts": dict(sorted(requirement_counts.items())),
        "suppressed_onet_requirements": suppressed,
    }


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--esco", type=Path, default=root / "data/raw/esco")
    parser.add_argument("--onet", type=Path, default=root / "data/raw/onet")
    parser.add_argument("--catalog", type=Path, default=root / "data/interim/concept_catalog_v1.jsonl")
    parser.add_argument(
        "--output", type=Path, default=root / "data/interim/occupation_benchmarks_v1.jsonl"
    )
    parser.add_argument(
        "--schema", type=Path, default=root / "data/schema/occupation-benchmark-v1.schema.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build(
        args.esco.resolve(), args.onet.resolve(), args.catalog.resolve(),
        args.output.resolve(), args.schema.resolve()
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"Wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
