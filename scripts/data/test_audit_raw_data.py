import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from audit_raw_data import FORBIDDEN_KEYS, jsonl_shape, nested_keys, parquet_shape


class RawDataAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_jsonl_shape_collects_union_of_keys(self):
        path = self.root / "records.json"
        path.write_text('{"tokens": [], "source": "a"}\n{"tokens": [], "tags": []}\n', encoding="utf-8")
        self.assertEqual(jsonl_shape(path), (2, ["source", "tags", "tokens"]))

    def test_parquet_shape_uses_metadata(self):
        path = self.root / "sample.parquet"
        pq.write_table(pa.table({"id": [1, 2], "text": ["a", "b"]}), path)
        self.assertEqual(parquet_shape(path), (2, ["id", "text"]))

    def test_nested_privacy_keys_are_detected(self):
        profile = {"user": {"age": 30}, "jobs": [{"city": "x"}], "skills": ["Python"]}
        self.assertEqual(set(nested_keys(profile)) & FORBIDDEN_KEYS, {"age", "city"})

    def test_jsonl_rejects_non_object_rows(self):
        path = self.root / "invalid.json"
        path.write_text(json.dumps([1, 2]) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a JSON object"):
            jsonl_shape(path)


if __name__ == "__main__":
    unittest.main()
