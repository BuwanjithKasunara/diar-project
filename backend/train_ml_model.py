"""Reproducible offline evaluation; model saving requires --save-model."""
import argparse
import hashlib
import json
import platform
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
import importlib.metadata

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from app.modules.ml_classifier import load_dataset, DATASET_PATH, MODEL_PATH

SEED = 42

def build_pipeline():
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=4000, sublinear_tf=True)),
        ("clf", LogisticRegression(C=1.5, max_iter=1000, random_state=SEED)),
    ])

def evaluate(output, save_model=False):
    texts, labels = load_dataset()
    unique = {}
    duplicates = 0
    for text, label in zip(texts, labels):
        key = re.sub(r"\s+", " ", text.casefold()).strip()
        if key in unique:
            if unique[key][1] != label:
                raise ValueError("Conflicting labels for duplicate profile text.")
            duplicates += 1
        else:
            unique[key] = (text, label)
    texts, labels = map(list, zip(*unique.values()))
    if min(Counter(labels).values()) < 5:
        raise ValueError("Evaluation needs at least five unique examples per class.")
    indices = list(range(len(texts)))
    train, test = train_test_split(indices, test_size=0.2, random_state=SEED, stratify=labels)
    pipeline = build_pipeline()
    pipeline.fit([texts[i] for i in train], [labels[i] for i in train])
    expected = [labels[i] for i in test]
    predicted = pipeline.predict([texts[i] for i in test])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    scores = cross_val_score(build_pipeline(), texts, labels, cv=cv)
    near_pairs = sum(SequenceMatcher(None, texts[i].casefold(), texts[j].casefold()).ratio() >= 0.9 for i in train for j in test)
    classes = sorted(set(labels))
    report = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": hashlib.sha256(Path(DATASET_PATH).read_bytes()).hexdigest(),
        "dataset_source": "Repository CSV; original source and collection method unknown",
        "dataset_license": "Unknown; no dataset-specific license evidence found",
        "python_version": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in ["scikit-learn", "numpy", "scipy", "joblib"]},
        "seed": SEED, "raw_rows": len(unique) + duplicates,
        "unique_rows": len(texts), "class_counts": dict(sorted(Counter(labels).items())),
        "normalized_duplicates_removed": duplicates, "conflicting_duplicate_labels": 0,
        "holdout": {"train_count": len(train), "test_count": len(test),
                    "train_indices": train, "test_indices": test,
                    "exact_text_overlap": len(set(train) & set(test)),
                    "near_duplicate_pairs_at_0_9": near_pairs,
                    "accuracy": float(accuracy_score(expected, predicted)),
                    "classification_report": classification_report(expected, predicted, output_dict=True, zero_division=0),
                    "confusion_matrix_labels": classes,
                    "confusion_matrix": confusion_matrix(expected, predicted, labels=classes).tolist()},
        "cross_validation": {"method": "5-fold stratified, shuffled; vectorizer fitted inside each fold", "scores": scores.tolist(), "mean": float(np.mean(scores)), "std": float(np.std(scores))},
        "configuration": {"ngram_range": [1, 2], "stop_words": "english", "max_features": 4000, "sublinear_tf": True, "C": 1.5, "max_iter": 1000},
        "limits": ["In-dataset results do not establish accuracy on real profiles or calibrated confidence.", "Exact duplicates are removed before splitting. Character similarity >=0.9 screens train/test near duplicates; semantic/template leakage and shared authors are not ruled out.", "Original provenance, consent, license and representativeness remain unverified.", "No low-probability abstention threshold is selected from this evaluation."],
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if save_model:
        final_model = build_pipeline().fit(texts, labels)
        joblib.dump(final_model, MODEL_PATH)
    print(json.dumps({"unique_rows": len(texts), "duplicates_removed": duplicates, "holdout_accuracy": report["holdout"]["accuracy"], "cv_mean": report["cross_validation"]["mean"], "evaluation": str(output), "model_saved": save_model}, indent=2))
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="../docs/testing/model-evaluation.json")
    parser.add_argument("--save-model", action="store_true", help="Also retrain and replace the local model artifact")
    args = parser.parse_args()
    evaluate(args.output, args.save_model)
