"""Build source-neutral DIAR central profiles from the filtered synthetic sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from jsonschema import Draft202012Validator


SCHEMA_VERSION = "1.0.0"


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(prefix: str, *parts: str) -> str:
    raw = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}-" + hashlib.sha256(raw).hexdigest()[:16]


def combined_text(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    values = [clean_text(item.get(field)) for field in fields]
    return " — ".join(value for value in values if value)


def validate_references(profile: dict[str, Any]) -> None:
    source_ids = [item["source_record_id"] for item in profile["source_records"]]
    evidence = profile["profile_evidence"]["evidence_units"]
    evidence_ids = [item["evidence_id"] for item in evidence]
    claim_ids = [item["claim_id"] for item in profile["profile_evidence"]["claims"]]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate source_record_id")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("duplicate evidence_id")
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("duplicate claim_id")
    unknown_sources = {item["source_record_id"] for item in evidence} - set(source_ids)
    if unknown_sources:
        raise ValueError(f"evidence references unknown source records: {sorted(unknown_sources)}")
    claim_evidence = {
        evidence_id
        for claim in profile["profile_evidence"]["claims"]
        for evidence_id in claim["evidence_ids"]
    }
    unknown_evidence = claim_evidence - set(evidence_ids)
    if unknown_evidence:
        raise ValueError(f"claims reference unknown evidence: {sorted(unknown_evidence)}")


def transform_row(row: dict[str, Any], validator: Draft202012Validator) -> dict[str, Any]:
    if row.get("source") != "synthetic":
        raise ValueError(f"unsupported source for {row.get('profile_id')}: {row.get('source')}")
    try:
        source_profile = json.loads(row["profile_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid profile_json for {row.get('profile_id')}") from exc
    if not isinstance(source_profile, dict):
        raise ValueError(f"profile_json for {row.get('profile_id')} is not an object")

    profile_id = clean_text(row["profile_id"])
    source_record_id = stable_id("src", "synthetic_profiles", profile_id)
    evidence_units: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    def add_evidence(artifact_type: str, text: str, locator: str) -> str | None:
        text = clean_text(text)
        if not text:
            return None
        evidence_id = stable_id("ev", profile_id, locator, text)
        evidence_units.append({
            "evidence_id": evidence_id,
            "source_record_id": source_record_id,
            "artifact_type": artifact_type,
            "text": text[:5000],
            "locator": locator,
            "extraction_method": "structured_field",
        })
        return evidence_id

    user = source_profile.get("user") if isinstance(source_profile.get("user"), dict) else {}
    seen_skills: set[str] = set()
    for index, value in enumerate(user.get("skills") or []):
        skill = clean_text(value)
        normalized = skill.casefold()
        if not normalized or normalized in seen_skills:
            continue
        seen_skills.add(normalized)
        locator = f"profile_json.user.skills[{index}]"
        evidence_id = add_evidence("stated_skill", skill, locator)
        if evidence_id:
            claims.append({
                "claim_id": stable_id("clm", profile_id, "skill", normalized),
                "category": "skill",
                "concept_text": skill,
                "normalized_text": normalized,
                "canonical_concept_id": None,
                "mapping_status": "unmapped",
                "mapping_candidates": [],
                "assertion": "claimed",
                "evidence_ids": [evidence_id],
            })

    add_evidence("profile_summary", user.get("bio"), "profile_json.user.bio")
    section_rules = {
        "experience": ("experience", ("title", "description")),
        "education": ("education", ("degree", "field_of_study", "description")),
        "projects": ("project", ("name", "description")),
        "certifications": ("certification", ("name", "description")),
        "awards": ("award", ("name", "title", "description")),
        "publications": ("publication", ("name", "title", "description")),
    }
    for section, (artifact_type, fields) in section_rules.items():
        values = source_profile.get(section) or []
        if not isinstance(values, list):
            raise ValueError(f"{section} for {profile_id} is not a list")
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                raise ValueError(f"{section}[{index}] for {profile_id} is not an object")
            add_evidence(artifact_type, combined_text(item, fields), f"profile_json.{section}[{index}]")

    central = {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "source_records": [{
            "source_record_id": source_record_id,
            "source_type": "synthetic_profile",
            "status": "analysed",
            "synthetic": True,
            "locator": f"synthetic_profiles_filtered.parquet#{profile_id}",
        }],
        "profile_evidence": {
            "claims": claims,
            "evidence_units": evidence_units,
        },
        "design_labels": {
            "excluded_from_model_input": True,
            "cohort": clean_text(row["cohort"]),
            "job_family": clean_text(row["job_family"]),
            "seniority": clean_text(row["seniority"]),
            "seed_role": clean_text(row["seed_role"]),
            "sample_group": clean_text(row["sample_group"]),
        },
    }
    validator.validate(central)
    validate_references(central)
    return central


def build(source_path: Path, output_path: Path, schema_path: Path) -> dict[str, int]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validator.check_schema(schema)
    table = pq.read_table(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile_count = claim_count = evidence_count = 0
    seen_profiles: set[str] = set()
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            for row in table.to_pylist():
                central = transform_row(row, validator)
                if central["profile_id"] in seen_profiles:
                    raise ValueError(f"duplicate profile_id: {central['profile_id']}")
                seen_profiles.add(central["profile_id"])
                stream.write(json.dumps(central, ensure_ascii=False, sort_keys=True) + "\n")
                profile_count += 1
                claim_count += len(central["profile_evidence"]["claims"])
                evidence_count += len(central["profile_evidence"]["evidence_units"])
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {"profiles": profile_count, "claims": claim_count, "evidence_units": evidence_count}


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "data/raw/synthetic_profiles/synthetic_profiles_filtered.parquet",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data/interim/central_profiles_v1.jsonl",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=root / "data/schema/central-profile-v1.schema.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build(args.source.resolve(), args.output.resolve(), args.schema.resolve())
    print(json.dumps(summary, sort_keys=True))
    print(f"Wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
