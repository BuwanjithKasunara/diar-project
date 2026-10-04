"""Map central-profile claims to exact ESCO/O*NET labels without fuzzy guessing."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number} is not an object")
                yield value


def build_index(catalog_path: Path) -> dict[str, list[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for concept in read_jsonl(catalog_path):
        for label in [concept["preferred_label"], *concept["aliases"]]:
            normalized = normalize(label)
            if normalized:
                index[normalized].add(concept["concept_id"])
    return {label: sorted(ids) for label, ids in index.items()}


def map_profile(profile: dict[str, Any], index: dict[str, list[str]]) -> Counter[str]:
    statuses: Counter[str] = Counter()
    for claim in profile["profile_evidence"]["claims"]:
        candidates = index.get(normalize(claim["normalized_text"]), [])
        claim["mapping_candidates"] = candidates
        if len(candidates) == 1:
            claim["mapping_status"] = "exact"
            claim["canonical_concept_id"] = candidates[0]
        elif candidates:
            claim["mapping_status"] = "ambiguous"
            claim["canonical_concept_id"] = None
        else:
            claim["mapping_status"] = "unmapped"
            claim["canonical_concept_id"] = None
        statuses[claim["mapping_status"]] += 1
    return statuses


def map_dataset(
    profiles_path: Path,
    catalog_path: Path,
    output_path: Path,
    report_path: Path,
    profile_schema_path: Path,
) -> dict[str, Any]:
    schema = json.loads(profile_schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validator.check_schema(schema)
    index = build_index(catalog_path)
    totals: Counter[str] = Counter()
    unique: dict[str, str] = {}
    claim_frequencies: Counter[str] = Counter()
    candidates_by_claim: dict[str, list[str]] = {}
    profile_count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            for profile in read_jsonl(profiles_path):
                totals.update(map_profile(profile, index))
                validator.validate(profile)
                for claim in profile["profile_evidence"]["claims"]:
                    unique[claim["normalized_text"]] = claim["mapping_status"]
                    claim_frequencies[claim["normalized_text"]] += 1
                    candidates_by_claim[claim["normalized_text"]] = claim["mapping_candidates"]
                stream.write(json.dumps(profile, ensure_ascii=False, sort_keys=True) + "\n")
                profile_count += 1
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    unique_counts = Counter(unique.values())
    total_claims = sum(totals.values())
    report = {
        "mapping_version": "1.0.0",
        "method": "case-insensitive exact match against preferred labels and aliases",
        "profiles": profile_count,
        "claim_instances": total_claims,
        "claim_instance_counts": dict(sorted(totals.items())),
        "claim_instance_exact_rate": round(totals["exact"] / total_claims, 6) if total_claims else None,
        "unique_claims": len(unique),
        "unique_claim_counts": dict(sorted(unique_counts.items())),
        "unique_claim_exact_rate": round(unique_counts["exact"] / len(unique), 6) if unique else None,
        "review_queue": {
            status: [
                {
                    "normalized_text": label,
                    "instances": claim_frequencies[label],
                    "mapping_candidates": candidates_by_claim[label],
                }
                for label in sorted(
                    (label for label, value in unique.items() if value == status),
                    key=lambda label: (-claim_frequencies[label], label),
                )[:50]
            ]
            for status in ("ambiguous", "unmapped")
        },
        "limitations": [
            "Exact matches are lexical mappings, not proof of equivalent proficiency.",
            "Ambiguous labels are not resolved automatically.",
            "Unmatched claims are retained and are not treated as absent knowledge.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=root / "data/interim/central_profiles_v1.jsonl")
    parser.add_argument("--catalog", type=Path, default=root / "data/interim/concept_catalog_v1.jsonl")
    parser.add_argument("--output", type=Path, default=root / "data/processed/central_profiles_mapped_v1.jsonl")
    parser.add_argument("--report", type=Path, default=root / "data/reports/concept-mapping-v1.json")
    parser.add_argument(
        "--profile-schema", type=Path, default=root / "data/schema/central-profile-v1.schema.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = map_dataset(
        args.profiles.resolve(),
        args.catalog.resolve(),
        args.output.resolve(),
        args.report.resolve(),
        args.profile_schema.resolve(),
    )
    console_summary = {key: value for key, value in report.items() if key != "review_queue"}
    print(json.dumps(console_summary, sort_keys=True))
    print(f"Wrote {args.output.resolve()}")
    print(f"Wrote {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
