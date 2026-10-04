"""Inventory DIAR raw datasets and validate the synthetic-profile design sample.

The command is deliberately read-only. It never rewrites source datasets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


SAMPLE_SEED = "20261004"
EXPECTED_GROUPS = {
    "software_engineering": 200,
    "data_science": 200,
    "research": 200,
    "product": 200,
    "entrepreneurial_adjacent": 200,
}
DIRECT_GROUP_FAMILIES = {
    "software_engineering": "software_engineering",
    "data_science": "data_science",
    "research": "research",
    "product": "product_management",
}
ENTREPRENEURIAL_ROLES = {
    "business development manager": 40,
    "business operations manager": 40,
    "growth marketer": 40,
    "strategy consultant": 40,
    "venture capital associate": 40,
}
FORBIDDEN_KEYS = {
    "age",
    "country",
    "desired_salary",
    "ethnicity",
    "experience_years",
    "legal_status",
    "salary",
    "sponsorship_needed",
    "state",
    "city",
    "visa_status",
    "work_location_preferences",
}


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def csv_shape(path: Path) -> tuple[int, list[str]]:
    # Taxonomy descriptions can exceed the csv module's small platform default.
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            break
        except OverflowError:
            limit //= 10
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        columns = next(reader, [])
        return sum(1 for _ in reader), columns


def jsonl_shape(path: Path) -> tuple[int, list[str]]:
    count = 0
    keys: set[str] = set()
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            keys.update(value)
            count += 1
    return count, sorted(keys)


def parquet_shape(path: Path) -> tuple[int, list[str]]:
    parquet = pq.ParquetFile(path)
    return parquet.metadata.num_rows, parquet.schema_arrow.names


def profile_file(path: Path, root: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        rows, columns = csv_shape(path)
        kind = "csv"
    elif suffix in {".json", ".jsonl"}:
        rows, columns = jsonl_shape(path)
        kind = "jsonl"
    elif suffix == ".parquet":
        rows, columns = parquet_shape(path)
        kind = "parquet"
    else:
        rows, columns, kind = None, [], "other"
    return {
        "path": path.relative_to(root).as_posix(),
        "format": kind,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "rows": rows,
        "columns": columns,
    }


def iter_dataset_files(raw_dir: Path) -> Iterable[Path]:
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or ".venv" in path.parts:
            continue
        if path.suffix.lower() in {".csv", ".json", ".jsonl", ".parquet", ".txt"}:
            yield path


def nested_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key.casefold()
            yield from nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_keys(child)


def validate_synthetic_sample(raw_dir: Path) -> dict[str, Any]:
    source_path = raw_dir / "synthetic_profiles" / "synthetic_profiles.parquet"
    sample_path = raw_dir / "synthetic_profiles" / "synthetic_profiles_filtered.parquet"
    errors: list[str] = []
    for path in (source_path, sample_path):
        if not path.is_file():
            errors.append(f"missing required file: {path}")
    if errors:
        return {"valid": False, "errors": errors}

    identity_columns = ["profile_id", "source", "cohort", "job_family", "seniority", "seed_role"]
    source = pq.read_table(source_path, columns=identity_columns)
    sample = pq.read_table(sample_path)
    source_by_id = {row["profile_id"]: row for row in source.to_pylist()}
    rows = sample.to_pylist()
    sample_ids = [row["profile_id"] for row in rows]

    if len(rows) != 1000:
        errors.append(f"expected 1000 sample rows, found {len(rows)}")
    if len(sample_ids) != len(set(sample_ids)):
        errors.append("sample profile_id values are not unique")
    missing_ids = set(sample_ids) - source_by_id.keys()
    if missing_ids:
        errors.append(f"{len(missing_ids)} sample profile_id values are absent from the source")
    changed_identity_rows = 0
    for row in rows:
        source_row = source_by_id.get(row["profile_id"])
        if source_row and any(row[column] != source_row[column] for column in identity_columns[1:]):
            changed_identity_rows += 1
    if changed_identity_rows:
        errors.append(f"{changed_identity_rows} sample rows change source identity fields")

    group_counts = Counter(row.get("sample_group") for row in rows)
    if dict(group_counts) != EXPECTED_GROUPS:
        errors.append(f"unexpected sample-group counts: {dict(group_counts)}")
    family_mismatches = Counter(
        row.get("sample_group")
        for row in rows
        if row.get("sample_group") in DIRECT_GROUP_FAMILIES
        and row.get("job_family") != DIRECT_GROUP_FAMILIES[row["sample_group"]]
    )
    if family_mismatches:
        errors.append(f"sample-group/job-family mismatches: {dict(family_mismatches)}")

    role_counts = Counter(
        row.get("seed_role")
        for row in rows
        if row.get("sample_group") == "entrepreneurial_adjacent"
    )
    if dict(role_counts) != ENTREPRENEURIAL_ROLES:
        errors.append(f"unexpected entrepreneurial-adjacent role counts: {dict(role_counts)}")

    invalid_json = 0
    forbidden_hits: Counter[str] = Counter()
    for row in rows:
        try:
            profile = json.loads(row["profile_json"])
        except (TypeError, json.JSONDecodeError):
            invalid_json += 1
            continue
        for key in set(nested_keys(profile)) & FORBIDDEN_KEYS:
            forbidden_hits[key] += 1
    if invalid_json:
        errors.append(f"{invalid_json} profile_json values are invalid")
    if forbidden_hits:
        errors.append(f"forbidden fields remain: {dict(forbidden_hits)}")
    if "country" in sample.column_names:
        errors.append("top-level country column remains in filtered sample")

    return {
        "valid": not errors,
        "errors": errors,
        "source_rows": pq.ParquetFile(source_path).metadata.num_rows,
        "sample_rows": len(rows),
        "sample_seed_documented": SAMPLE_SEED,
        "sample_groups": dict(sorted(group_counts.items())),
        "entrepreneurial_adjacent_roles": dict(sorted(role_counts.items())),
        "sample_columns": sample.column_names,
        "invalid_profile_json": invalid_json,
        "forbidden_field_hits": dict(forbidden_hits),
        "changed_identity_rows": changed_identity_rows,
        "direct_group_family_mismatches": dict(family_mismatches),
    }


def build_report(root: Path) -> dict[str, Any]:
    raw_dir = root / "data" / "raw"
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"raw data directory not found: {raw_dir}")
    files = [profile_file(path, root) for path in iter_dataset_files(raw_dir)]
    return {
        "schema_version": 1,
        "raw_directory": raw_dir.relative_to(root).as_posix(),
        "file_count": len(files),
        "files": files,
        "synthetic_profile_validation": validate_synthetic_sample(raw_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2], help="repository root"
    )
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    report = build_report(root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {output}")
    else:
        print(rendered, end="")
    validation = report["synthetic_profile_validation"]
    if not validation["valid"]:
        for error in validation["errors"]:
            print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
