import csv
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from build_occupation_benchmarks import build, numeric


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data/schema/occupation-benchmark-v1.schema.json"


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class OccupationBenchmarkBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.esco = self.root / "esco"
        self.onet = self.root / "onet"
        self.catalog = self.root / "catalog.jsonl"
        entries = [
            {"concept_id": "esco:s1", "category": "skill"},
            {"concept_id": "onet:2.A.1", "category": "skill"},
        ]
        self.catalog.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")

        write_csv(
            self.esco / "occupations_en.csv",
            ["conceptUri", "preferredLabel", "description"],
            [{"conceptUri": "http://example/o1", "preferredLabel": "Engineer", "description": "Builds."}],
        )
        write_csv(
            self.esco / "occupationSkillRelations_en.csv",
            ["occupationUri", "skillUri", "relationType"],
            [
                {"occupationUri": "http://example/o1", "skillUri": "http://example/s1", "relationType": "optional"},
                {"occupationUri": "http://example/o1", "skillUri": "http://example/s1", "relationType": "essential"},
            ],
        )
        write_csv(
            self.onet / "occupation_data.csv",
            ["O*NET-SOC Code", "Title", "Description"],
            [{"O*NET-SOC Code": "11-0000.00", "Title": "Manager", "Description": "Manages."}],
        )
        rating_columns = [
            "O*NET-SOC Code", "Element ID", "Scale ID", "Data Value", "Recommend Suppress", "Not Relevant"
        ]
        write_csv(
            self.onet / "essential_skills.csv",
            rating_columns,
            [
                {"O*NET-SOC Code": "11-0000.00", "Element ID": "2.A.1", "Scale ID": "IM", "Data Value": "4.2", "Recommend Suppress": "N", "Not Relevant": ""},
                {"O*NET-SOC Code": "11-0000.00", "Element ID": "2.A.1", "Scale ID": "LV", "Data Value": "5.1", "Recommend Suppress": "Y", "Not Relevant": "N"},
            ],
        )
        write_csv(self.onet / "knowledge.csv", rating_columns, [])
        write_csv(
            self.onet / "software_skills.csv",
            ["O*NET-SOC Code", "Element ID", "Workplace Example", "Hot Technology", "In Demand"],
            [],
        )

    def test_build_preserves_sources_and_suppression(self):
        output = self.root / "benchmarks.jsonl"
        summary = build(self.esco, self.onet, self.catalog, output, SCHEMA_PATH)
        self.assertEqual(summary["benchmarks"], 2)
        records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        for record in records:
            validator.validate(record)
        esco, onet = records
        self.assertEqual(esco["requirements"][0]["relationship"], "essential")
        rating = onet["requirements"][0]
        self.assertTrue(rating["suppressed"])
        self.assertIsNone(rating["importance"])
        self.assertIsNone(rating["level"])
        self.assertFalse(rating["not_relevant"])

    def test_numeric_rejects_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "invalid numeric value"):
            numeric("not-a-number")


if __name__ == "__main__":
    unittest.main()
