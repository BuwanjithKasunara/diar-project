import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from jsonschema import Draft202012Validator

from build_central_profiles import build, transform_row, validate_references


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data/schema/central-profile-v1.schema.json"


def fixture_row():
    return {
        "profile_id": "synthetic-1",
        "source": "synthetic",
        "cohort": "entry_level",
        "job_family": "software_engineering",
        "seniority": "entry",
        "seed_role": "developer",
        "sample_group": "software_engineering",
        "profile_json": json.dumps({
            "user": {
                "skills": ["Python", " python ", "SQL"],
                "languages": ["English"],
                "bio": "Builds data services.",
                "career_interests": ["Engineering Manager"],
            },
            "experience": [{
                "company": "Private Employer",
                "title": "Developer",
                "start_date": "01/2020",
                "end_date": None,
                "description": "Built an API.",
                "is_internship": False,
            }],
            "education": [{
                "school": "Private University",
                "degree": "BSc",
                "field_of_study": "Computing",
                "start_date": "01/2016",
                "end_date": "01/2020",
                "is_current": False,
                "gpa": 4.0,
                "description": None,
            }],
            "projects": [],
            "certifications": [],
            "awards": [],
            "publications": [],
        }),
    }


class CentralProfileBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(schema)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_transform_is_valid_deterministic_and_deduplicates_skills(self):
        first = transform_row(fixture_row(), self.validator)
        second = transform_row(fixture_row(), self.validator)
        self.assertEqual(first, second)
        self.assertEqual(
            [claim["normalized_text"] for claim in first["profile_evidence"]["claims"]],
            ["python", "sql"],
        )
        self.assertTrue(first["design_labels"]["excluded_from_model_input"])

    def test_transform_excludes_non_professional_and_direct_identifier_fields(self):
        profile = transform_row(fixture_row(), self.validator)
        evidence = json.dumps(profile["profile_evidence"])
        for excluded in (
            "Private Employer", "Private University", "01/2020", "4.0", "English", "Engineering Manager"
        ):
            self.assertNotIn(excluded, evidence)
        self.assertIn("Built an API", evidence)
        self.assertIn("Computing", evidence)

    def test_build_writes_valid_json_lines(self):
        source = self.root / "source.parquet"
        output = self.root / "central.jsonl"
        pq.write_table(pa.Table.from_pylist([fixture_row()]), source)
        summary = build(source, output, SCHEMA_PATH)
        self.assertEqual(summary["profiles"], 1)
        records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 1)
        self.validator.validate(records[0])

    def test_invalid_profile_json_is_rejected(self):
        row = fixture_row()
        row["profile_json"] = "not json"
        with self.assertRaisesRegex(ValueError, "invalid profile_json"):
            transform_row(row, self.validator)

    def test_cross_references_are_enforced(self):
        profile = transform_row(fixture_row(), self.validator)
        profile["profile_evidence"]["claims"][0]["evidence_ids"] = ["ev-0000000000000000"]
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            validate_references(profile)

    def test_unsupported_source_is_rejected(self):
        row = fixture_row()
        row["source"] = "resume"
        with self.assertRaisesRegex(ValueError, "unsupported source"):
            transform_row(row, self.validator)


if __name__ == "__main__":
    unittest.main()
