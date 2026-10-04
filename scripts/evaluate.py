"""Print extraction regression metrics as JSON. Does not write files or call services."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.modules.extraction import _find_skills


def metrics(cases):
    tp = fp = fn = exact = 0
    errors = []
    for identifier, expected, predicted in cases:
        expected, predicted = set(expected), set(predicted)
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        exact += expected == predicted
        if expected != predicted:
            errors.append({"id": identifier, "false_positives": sorted(predicted - expected),
                           "false_negatives": sorted(expected - predicted)})
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"cases": len(cases), "true_positives": tp, "false_positives": fp,
            "false_negatives": fn, "micro_precision": precision, "micro_recall": recall,
            "exact_matches": exact, "exact_match_rate": exact / len(cases) if cases else None,
            "errors": errors}


def evaluate():
    fixtures = ROOT / "backend" / "tests" / "fixtures"
    baseline = json.loads((fixtures / "baseline.json").read_text(encoding="utf-8"))
    profiles = json.loads((fixtures / "profiles.json").read_text(encoding="utf-8"))
    focused = baseline["cases"]
    matrix = profiles["profiles"]
    return {
        "baseline_revision": baseline["revision"],
        "baseline_dataset_version": baseline["dataset_version"],
        "profile_dataset_version": profiles["dataset_version"],
        "focused_baseline": metrics([(c["text"], c["expected"], c["baseline"]) for c in focused]),
        "focused_current": metrics([(c["text"], c["expected"], _find_skills(c["text"])) for c in focused]),
        "profile_matrix_current": metrics([(c["id"], c["expected_skills"], _find_skills(c["linkedin_text"])) for c in matrix]),
        "limitations": "Authored synthetic development regressions, not held-out evaluation. Baseline outputs exist only for the six focused cases. No baseline comparison is claimed for the 30-profile matrix. Null metrics mean their denominator is zero."
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
