"""Print extraction regression metrics as JSON. Does not write files or call services."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.modules.extraction import _find_skills
from app import main
from app.modules import alignment_engine, extraction, identity_construction, recommendation_engine


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


def macro_metrics(cases):
    rows = []
    for identifier, expected, predicted in cases:
        expected, predicted = set(expected), set(predicted)
        tp = len(expected & predicted)
        precision = tp / len(predicted) if predicted else (1.0 if not expected else 0.0)
        recall = tp / len(expected) if expected else (1.0 if not predicted else 0.0)
        rows.append((precision, recall))
    return {
        "cases": len(rows),
        "macro_precision": sum(p for p, _ in rows) / len(rows) if rows else None,
        "macro_recall": sum(r for _, r in rows) / len(rows) if rows else None,
    }


def _missing_source(name, failed=False):
    return {"source": name, "source_status": extraction.status("failed" if failed else "not_supplied",
                                                                  "Synthetic failure." if failed else None)}


def _assessment(case):
    if case["kind"] == "insufficient":
        failed = case.get("failed", False)
        profile = identity_construction.build_digital_identity_profile(
            _missing_source("resume", failed), _missing_source("github", failed),
            _missing_source("linkedin", failed))
    else:
        linkedin = extraction.extract_from_linkedin_text(case.get("text", ""), "unverified")
        profile = identity_construction.build_digital_identity_profile(
            _missing_source("resume"), _missing_source("github"), linkedin)
    aligned = alignment_engine.run_alignment(profile, main.BENCHMARKS[case["role"]], case["role"],
                                             "Privacy Focused")
    recommendations = recommendation_engine.generate_recommendations(aligned["fired_rules"])
    return aligned, recommendations


def v3_metrics(dataset):
    extraction_cases = [(case["id"], case["expected_skills"], _find_skills(case["text"]))
                        for case in dataset["extraction_cases"]]
    extraction_result = {**metrics(extraction_cases), **macro_metrics(extraction_cases)}
    strong = adversarial = insufficient = absence = 0
    strong_ok = adversarial_ok = insufficient_ok = absence_ok = 0
    details = []
    for case in dataset["assessment_cases"]:
        aligned, recommendations = _assessment(case)
        summary = aligned["assessment"]["benchmark_evidence"]
        evidenced = summary["evidenced_count"]
        states = {r["id"]: r["state"] for r in summary["capability_results"]}
        kind, passed = case["kind"], True
        if kind == "strong_evidence":
            strong += 1
            passed = evidenced >= case["minimum_evidenced_capabilities"]
            strong_ok += passed
        elif kind == "adversarial":
            adversarial += 1
            passed = evidenced <= case["maximum_evidenced_capabilities"]
            adversarial_ok += passed
        elif kind == "insufficient":
            insufficient += 1
            passed = summary["score"] is None and set(states.values()) == {"not_assessed"}
            insufficient_ok += passed
        elif kind == "absence_only":
            absence += 1
            confirmed = sum(r["action"].startswith("recommend_learning:") for r in aligned["fired_rules"])
            passed = confirmed <= case["maximum_confirmed_gap_recommendations"]
            absence_ok += passed
        elif kind == "explicit_gap":
            passed = states.get(case["expected_explicit_gap"]) == "explicit_gap"
        details.append({"id": case["id"], "kind": kind, "passed": bool(passed),
                        "evidenced_capabilities": evidenced,
                        "recommendations": [r["rule_id"] for r in recommendations]})
    rates = {
        "strong_evidence_non_limited_rate": strong_ok / strong if strong else None,
        "adversarial_non_broad_rate": adversarial_ok / adversarial if adversarial else None,
        "insufficient_not_assessed_rate": insufficient_ok / insufficient if insufficient else None,
        "absence_only_gap_wording_rate": 1 - (absence_ok / absence) if absence else None,
    }
    gates = dataset["acceptance_gates"]
    gate_results = {
        "macro_precision": extraction_result["macro_precision"] >= gates["macro_precision"],
        "macro_recall": extraction_result["macro_recall"] >= gates["macro_recall"],
        "strong_evidence_non_limited_rate": rates["strong_evidence_non_limited_rate"] >= gates["strong_evidence_non_limited_rate"],
        "adversarial_non_broad_rate": rates["adversarial_non_broad_rate"] >= gates["adversarial_non_broad_rate"],
        "insufficient_not_assessed_rate": rates["insufficient_not_assessed_rate"] >= gates["insufficient_not_assessed_rate"],
        "absence_only_gap_wording_rate": rates["absence_only_gap_wording_rate"] <= gates["absence_only_gap_wording_rate"],
    }
    return {"dataset_version": dataset["dataset_version"], "extraction": extraction_result,
            "assessment_rates": rates, "gate_results": gate_results,
            "all_gates_pass": all(gate_results.values()) and all(d["passed"] for d in details),
            "case_results": details,
            "limitations": dataset["provenance"]}


def evaluate():
    fixtures = ROOT / "backend" / "tests" / "fixtures"
    baseline = json.loads((fixtures / "baseline.json").read_text(encoding="utf-8"))
    profiles = json.loads((fixtures / "profiles.json").read_text(encoding="utf-8"))
    evaluation_v3 = json.loads((fixtures / "evaluation_v3.json").read_text(encoding="utf-8"))
    focused = baseline["cases"]
    matrix = profiles["profiles"]
    return {
        "baseline_revision": baseline["revision"],
        "baseline_dataset_version": baseline["dataset_version"],
        "profile_dataset_version": profiles["dataset_version"],
        "focused_baseline": metrics([(c["text"], c["expected"], c["baseline"]) for c in focused]),
        "focused_current": metrics([(c["text"], c["expected"], _find_skills(c["text"])) for c in focused]),
        "profile_matrix_current": metrics([(c["id"], c["expected_skills"], _find_skills(c["linkedin_text"])) for c in matrix]),
        "version_3": v3_metrics(evaluation_v3),
        "limitations": "Authored synthetic development regressions, not held-out evaluation. Baseline outputs exist only for the six focused cases. No baseline comparison is claimed for the 30-profile matrix. Null metrics mean their denominator is zero."
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
