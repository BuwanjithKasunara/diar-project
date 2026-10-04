import json
import tempfile
import unittest
from pathlib import Path

from build_concept_catalog import esco_entries, unique_text
from map_central_claims import build_index, map_profile, normalize


class ConceptMappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_unique_text_normalizes_case_and_whitespace(self):
        self.assertEqual(unique_text([" PyTorch ", "pytorch", "Torch"], "PYTORCH"), ["Torch"])

    def test_esco_entry_preserves_identifier_aliases_and_category(self):
        path = self.root / "skills.csv"
        path.write_text(
            "conceptUri,preferredLabel,altLabels,skillType,description\n"
            'http://example/abc,Machine learning,"ML\nstatistical learning",knowledge,Models\n',
            encoding="utf-8",
        )
        entry = list(esco_entries(path))[0]
        self.assertEqual(entry["concept_id"], "esco:abc")
        self.assertEqual(entry["category"], "knowledge")
        self.assertEqual(entry["aliases"], ["ML", "statistical learning"])

    def test_identical_duplicate_esco_rows_are_collapsed(self):
        path = self.root / "skills.csv"
        header = "conceptUri,preferredLabel,altLabels,skillType,description\n"
        row = "http://example/abc,Python,,skill/competence,Programming\n"
        path.write_text(header + row + row, encoding="utf-8")
        self.assertEqual(len(list(esco_entries(path))), 1)

    def test_conflicting_duplicate_esco_rows_are_rejected(self):
        path = self.root / "skills.csv"
        path.write_text(
            "conceptUri,preferredLabel,altLabels,skillType,description\n"
            "http://example/abc,Python,,skill/competence,Programming\n"
            "http://example/abc,Python language,,skill/competence,Programming\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "conflicting ESCO rows"):
            list(esco_entries(path))

    def test_exact_ambiguous_and_unmapped_claims_are_distinct(self):
        catalog = self.root / "catalog.jsonl"
        entries = [
            {"concept_id": "esco:python", "preferred_label": "Python", "aliases": []},
            {"concept_id": "esco:ml", "preferred_label": "Machine learning", "aliases": ["ML"]},
            {"concept_id": "onet:ml", "preferred_label": "ML", "aliases": []},
        ]
        catalog.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
        profile = {"profile_evidence": {"claims": [
            {"normalized_text": "python"},
            {"normalized_text": "ML"},
            {"normalized_text": "unlisted"},
        ]}}
        counts = map_profile(profile, build_index(catalog))
        claims = profile["profile_evidence"]["claims"]
        self.assertEqual(counts, {"exact": 1, "ambiguous": 1, "unmapped": 1})
        self.assertEqual(claims[0]["canonical_concept_id"], "esco:python")
        self.assertIsNone(claims[1]["canonical_concept_id"])
        self.assertEqual(claims[1]["mapping_candidates"], ["esco:ml", "onet:ml"])
        self.assertEqual(claims[2]["mapping_candidates"], [])

    def test_normalize_is_case_and_whitespace_only(self):
        self.assertEqual(normalize("  C++   Programming "), "c++ programming")
        self.assertNotEqual(normalize("node.js"), normalize("nodejs"))


if __name__ == "__main__":
    unittest.main()
