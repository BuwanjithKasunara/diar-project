"""Focused checks for documentation gate; all fixtures live in temporary folders."""
import tempfile
import unittest
from pathlib import Path
from check_docs import check


class DocumentationCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs" / "adr").mkdir(parents=True)
        (self.root / "README.md").write_text("# Project", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("# Instructions", encoding="utf-8")

    def test_valid_relative_encoded_and_external_links(self):
        (self.root / "docs" / "with space.md").write_text("# Topic", encoding="utf-8")
        (self.root / "README.md").write_text(
            "[topic](docs/with%20space.md) [external](https://example.org/x)\n"
            "```text\n[illustration](not-a-real-file.md)\n```", encoding="utf-8")
        self.assertEqual(check(self.root), [])

    def test_missing_target_is_reported(self):
        (self.root / "README.md").write_text("[missing](docs/missing.md)", encoding="utf-8")
        self.assertEqual(len(check(self.root)), 1)
        self.assertIn("missing target", check(self.root)[0])

    def test_duplicate_adr_number_is_reported(self):
        for name in ("0001-first.md", "0001-second.md"):
            (self.root / "docs" / "adr" / name).write_text("# ADR", encoding="utf-8")
        self.assertEqual(len(check(self.root)), 1)
        self.assertIn("Duplicate ADR 0001", check(self.root)[0])


if __name__ == "__main__":
    unittest.main()
