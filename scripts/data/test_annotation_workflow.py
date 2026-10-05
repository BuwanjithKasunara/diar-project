import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from create_review_templates import create_templates
from export_blind_adjudication import export_blind_queue
from prepare_annotation_batches import level_tasks, mapping_tasks, write_jsonl
from prepare_expanded_level_batch import prepare_expanded_batch
from review_annotations import reconcile, validate_annotation


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "data/schema/review-annotation-v1.schema.json"
GROUPS = (
    "software_engineering", "data_science", "research", "product", "entrepreneurial_adjacent"
)


def profile(group, number, direct):
    profile_id = f"synthetic-{group}-{number}"
    skill_id = f"ev-{number:016x}"
    context_id = f"ev-{number + 100:016x}"
    context = "Built a Python service with tests." if direct else "Built a service with tests."
    return {
        "profile_id": profile_id,
        "design_labels": {"sample_group": group, "seniority": "senior"},
        "profile_evidence": {
            "claims": [{
                "claim_id": f"clm-{number:016x}",
                "normalized_text": "python",
                "concept_text": "Python",
                "mapping_status": "exact",
                "mapping_candidates": ["esco:python"],
                "evidence_ids": [skill_id],
            }],
            "evidence_units": [
                {"evidence_id": skill_id, "artifact_type": "stated_skill", "text": "Python"},
                {"evidence_id": context_id, "artifact_type": "project", "text": context},
            ],
        },
    }


def answer(task, reviewer, level, supporting_ids):
    return {
        "annotation_version": "1.0.0",
        "kind": "level",
        "task_id": task["task_id"],
        "task_digest": task["task_digest"],
        "reviewer_id": reviewer,
        "level": level,
        "supporting_evidence_ids": supporting_ids,
        "rationale": "Evidence supports this level.",
    }


class AnnotationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_packets_hide_generation_labels_and_balance_evidence_cases(self):
        profiles = [profile(group, index * 2 + direct + 1, bool(direct))
                    for index, group in enumerate(GROUPS) for direct in (0, 1)]
        catalog = {"esco:python": {
            "preferred_label": "Python", "category": "skill", "description": "A language"
        }}
        mapping, internal_map = mapping_tasks(
            profiles, catalog, {"ambiguous": 0, "unmapped": 0, "exact": 1}
        )
        levels, internal_level = level_tasks(profiles, per_group=2)
        self.assertEqual(len(mapping), 1)
        self.assertEqual(len(levels), 10)
        self.assertEqual({item["direct_text_match"] for item in internal_level}, {True, False})
        self.assertEqual({item["sample_group"] for item in internal_level}, set(GROUPS))
        self.assertNotIn("lexical_status", mapping[0])
        self.assertIn("lexical_status", internal_map[0])
        for task in mapping + levels:
            for forbidden in ("profile_id", "sample_group", "seniority", "design_labels"):
                self.assertNotIn(forbidden, task)
            self.assertEqual(len(task["task_digest"]), 20)

    def test_positive_level_requires_professional_evidence_and_fresh_digest(self):
        task = level_tasks([profile(group, index + 1, True) for index, group in enumerate(GROUPS)], 1)[0][0]
        statement_id = task["evidence"][0]["evidence_id"]
        project_id = task["evidence"][1]["evidence_id"]
        item = answer(task, "reviewer-one", "applied", [statement_id])
        with self.assertRaisesRegex(ValueError, "professional evidence"):
            validate_annotation(item, task, "level", self.validator, set())
        item["supporting_evidence_ids"] = [project_id]
        validate_annotation(item, task, "level", self.validator, set())
        item["task_digest"] = "0" * 20
        with self.assertRaisesRegex(ValueError, "stale task digest"):
            validate_annotation(item, task, "level", self.validator, set())

    def test_mapping_review_checks_catalogue_and_decision_shape(self):
        task = {
            "annotation_version": "1.0.0",
            "kind": "mapping",
            "task_id": "map-" + "a" * 20,
            "task_digest": "b" * 20,
            "claim_text": "python",
            "candidate_concepts": [],
            "sample_contexts": [],
        }
        item = {
            "annotation_version": "1.0.0",
            "kind": "mapping",
            "task_id": task["task_id"],
            "task_digest": task["task_digest"],
            "reviewer_id": "reviewer-one",
            "decision": "single_match",
            "concept_ids": ["esco:python"],
            "rationale": "The definition matches the claim.",
        }
        validate_annotation(item, task, "mapping", self.validator, {"esco:python"})
        with self.assertRaisesRegex(ValueError, "unknown catalogue"):
            validate_annotation(item, task, "mapping", self.validator, set())
        item["decision"] = "multiple_valid"
        with self.assertRaisesRegex(ValueError, "invalid concept count"):
            validate_annotation(item, task, "mapping", self.validator, {"esco:python"})

    def test_disagreement_requires_third_reviewer_and_keeps_sources(self):
        task = level_tasks([profile(group, index + 1, True) for index, group in enumerate(GROUPS)], 1)[0][0]
        tasks_path = self.root / "tasks.jsonl"
        first_path = self.root / "first.jsonl"
        second_path = self.root / "second.jsonl"
        third_path = self.root / "third.jsonl"
        write_jsonl(tasks_path, [task], replace=False)
        write_jsonl(first_path, [answer(task, "reviewer-one", "insufficient_evidence", [])], replace=False)
        write_jsonl(second_path, [answer(task, "reviewer-two", "applied", [task["evidence"][1]["evidence_id"]])], replace=False)
        out = self.root / "result"
        report = reconcile("level", tasks_path, first_path, second_path, out, SCHEMA)
        self.assertEqual(report["initial_disagreements"], 1)
        self.assertEqual(report["pending_adjudication"], 1)
        self.assertEqual((out / "resolved.jsonl").read_text(encoding="utf-8"), "")
        write_jsonl(third_path, [answer(task, "reviewer-three", "applied", [task["evidence"][1]["evidence_id"]])], replace=False)
        report = reconcile(
            "level", tasks_path, first_path, second_path, out, SCHEMA,
            adjudication_path=third_path, replace=True,
        )
        self.assertEqual(report["pending_adjudication"], 0)
        resolved = json.loads((out / "resolved.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(resolved["decision_source"], "adjudication")
        self.assertEqual(len(resolved["source_annotations"]), 3)
        self.assertFalse(report["training_ready"])

    def test_template_refresh_refuses_to_erase_an_answer(self):
        task = level_tasks([profile(group, index + 1, True) for index, group in enumerate(GROUPS)], 1)[0][0]
        tasks_path = self.root / "tasks.jsonl"
        write_jsonl(tasks_path, [task], replace=False)
        destination = self.root / "templates"
        create_templates(tasks_path, destination, "level")
        first = destination / "level_reviewer-a.jsonl"
        item = json.loads(first.read_text(encoding="utf-8"))
        item["rationale"] = "Human answer has been entered."
        write_jsonl(first, [item], replace=True)
        with self.assertRaisesRegex(ValueError, "human edits"):
            create_templates(tasks_path, destination, "level", refresh_unanswered=True)

    def test_single_adjudicator_template_uses_blind_tasks(self):
        task = level_tasks([profile(group, index + 1, True) for index, group in enumerate(GROUPS)], 1)[0][0]
        tasks_path = self.root / "blind-tasks.jsonl"
        write_jsonl(tasks_path, [task], replace=False)
        destination = self.root / "adjudicator"
        summary = create_templates(
            tasks_path, destination, "level", reviewer_names=("human-adjudicator",),
        )
        self.assertEqual(summary, {"tasks": 1, "reviewer_files": 1})
        item = json.loads((destination / "level_human-adjudicator.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(item["task_digest"], task["task_digest"])
        self.assertEqual(item["reviewer_id"], "")
        self.assertNotIn("first_annotation", item)
        with self.assertRaisesRegex(ValueError, "filename-safe"):
            create_templates(tasks_path, destination, "level", reviewer_names=("../outside",))

    def test_blind_adjudication_export_omits_prior_answers(self):
        task = level_tasks([profile(group, index + 1, True) for index, group in enumerate(GROUPS)], 1)[0][0]
        tasks_path = self.root / "tasks.jsonl"
        queue_path = self.root / "queue.jsonl"
        output_path = self.root / "blind.jsonl"
        write_jsonl(tasks_path, [task], replace=False)
        write_jsonl(queue_path, [{
            "task": task,
            "first_annotation": answer(task, "reviewer-one", "applied", [task["evidence"][1]["evidence_id"]]),
            "second_annotation": answer(task, "reviewer-two", "insufficient_evidence", []),
        }], replace=False)
        result = export_blind_queue(queue_path, tasks_path, output_path, "level")
        self.assertEqual(result["tasks"], 1)
        self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), task)
        with self.assertRaises(FileExistsError):
            export_blind_queue(queue_path, tasks_path, output_path, "level")

    def test_expanded_batch_excludes_pilot_profiles(self):
        profiles = []
        excluded = []
        for index, group in enumerate(GROUPS):
            pilot = profile(group, index * 10 + 1, False)
            profiles.extend([
                pilot,
                profile(group, index * 10 + 2, True),
                profile(group, index * 10 + 3, False),
            ])
            excluded.append({"profile_id": pilot["profile_id"]})
        profiles_path = self.root / "profiles.jsonl"
        excluded_path = self.root / "pilot-manifest.jsonl"
        write_jsonl(profiles_path, profiles, replace=False)
        write_jsonl(excluded_path, excluded, replace=False)
        output_dir = self.root / "expanded"
        summary = prepare_expanded_batch(profiles_path, excluded_path, output_dir, per_group=2)
        self.assertEqual(summary["level_task_count"], 10)
        self.assertEqual(summary["human_labels_assigned"], 0)
        public = [json.loads(line) for line in (output_dir / "level_tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        internal = [json.loads(line) for line in (output_dir / "level_internal_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(public), 10)
        self.assertFalse({row["profile_id"] for row in internal} & {row["profile_id"] for row in excluded})
        self.assertTrue(all("profile_id" not in task for task in public))
        with self.assertRaises(FileExistsError):
            prepare_expanded_batch(profiles_path, excluded_path, output_dir, per_group=2)


if __name__ == "__main__":
    unittest.main()
