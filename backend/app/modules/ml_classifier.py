"""
Machine Learning Role Classification Module
-------------------------------------------
Uses Natural Language Processing (TF-IDF Vectorization) and a
Supervised Machine Learning Classifier (Logistic Regression / Multinomial Softmax)
trained on a benchmark dataset of professional profiles and resumes.

Given a user's consolidated profile text, this module:
1. Predicts the closest benchmark professional identity (AI Engineer, Data Scientist,
   Software Engineer, Researcher, Entrepreneur).
2. Computes model probabilities across roles; calibration has not been established.
3. Lists matching vocabulary, ranked by TF-IDF weight, without claiming class contributions.
"""
import os
import csv
import logging
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATASET_PATH = os.path.join(DATA_DIR, "career_profiles_dataset.csv")
MODEL_PATH = os.path.join(DATA_DIR, "career_classifier.joblib")

_MODEL_PIPELINE = None
_MODEL_LOCK = threading.Lock()


def load_dataset(csv_path: str = DATASET_PATH) -> tuple[List[str], List[str]]:
    """Loads texts and labels from career_profiles_dataset.csv."""
    texts = []
    labels = []
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = row.get("role", "").strip()
            text = row.get("text", "").strip()
            if role and text:
                texts.append(text)
                labels.append(role)
    return texts, labels


def train_model(save: bool = True):
    """
    Trains a TF-IDF + Logistic Regression classification pipeline on the dataset
    and optionally persists it to disk using joblib.
    """
    global _MODEL_PIPELINE
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
    except ImportError:
        logger.warning("scikit-learn is not installed. ML classifier unavailable.")
        return None

    texts, labels = load_dataset()
    if not texts:
        logger.warning("Dataset is empty. Cannot train model.")
        return None

    # Pipeline: N-gram TF-IDF vectorizer + Multinomial Logistic Regression
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_features=4000,
            sublinear_tf=True
        )),
        ("clf", LogisticRegression(
            C=1.5,
            max_iter=1000,
            random_state=42
        ))
    ])

    pipeline.fit(texts, labels)
    _MODEL_PIPELINE = pipeline

    if save:
        try:
            try:
                import joblib
                joblib.dump(pipeline, MODEL_PATH)
            except ImportError:
                import pickle
                with open(MODEL_PATH, "wb") as f:
                    pickle.dump(pipeline, f)
            logger.info(f"Model saved successfully to {MODEL_PATH}")
        except Exception as e:
            logger.error(f"Failed to save model to disk: {e}")

    return pipeline


def get_model():
    # Prevent concurrent requests from loading/training/writing the same artifact.
    with _MODEL_LOCK:
        return _get_model_unlocked()


def _get_model_unlocked():
    """Returns the cached model, loads from disk, or trains on-the-fly."""
    global _MODEL_PIPELINE
    if _MODEL_PIPELINE is not None:
        return _MODEL_PIPELINE

    if os.path.exists(MODEL_PATH):
        try:
            try:
                import joblib
                _MODEL_PIPELINE = joblib.load(MODEL_PATH)
            except ImportError:
                import pickle
                with open(MODEL_PATH, "rb") as f:
                    _MODEL_PIPELINE = pickle.load(f)
            return _MODEL_PIPELINE
        except Exception as e:
            logger.warning(f"Failed loading model from {MODEL_PATH}: {e}. Retraining...")

    return train_model(save=True)


def _no_prediction(status, note, available=False):
    return {"model_available": available, "prediction_status": status,
            "predicted_role": "Undetermined" if status == "insufficient_evidence" else "Unavailable",
            "confidence": 0.0, "probabilities": {}, "matches_target": False,
            "top_features": [], "target_benchmark_probability": None,
            "feature_explanation_method": "matching_vocabulary", "note": note}


def predict_role(text: str, target_benchmark: Optional[str] = None) -> Dict[str, Any]:
    """Probabilities are not calibrated confidence; features are matching vocabulary.

    Active terms are ranked by TF-IDF weight, then name, not class contributions.
    """
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return _no_prediction("insufficient_evidence", "No text supplied for ML role analysis.")
    try:
        model = get_model()
        if model is None:
            return _no_prediction("unavailable", "ML model unavailable; rule analysis remains available.")
        vectorizer = model.named_steps["tfidf"]
        vector = vectorizer.transform([cleaned_text])
        if vector.nnz == 0:
            return _no_prediction("insufficient_evidence", "No trained model vocabulary matched; no role is assigned.", True)
        names = vectorizer.get_feature_names_out()
        weighted = [(str(names[i]), float(w)) for i, w in zip(vector.indices, vector.data)]
        features = [name for name, weight in sorted(weighted, key=lambda item: (-item[1], item[0]))[:8]]
        classes = [str(value) for value in model.classes_]
        probs = model.predict_proba([cleaned_text])[0]
        winner = max(range(len(classes)), key=lambda i: float(probs[i]))
        role = classes[winner]
        distribution = {name: round(float(prob), 4) for name, prob in zip(classes, probs)}
        target = next((name for name in classes if target_benchmark and name.casefold() == target_benchmark.casefold()), None)
        return {"model_available": True, "prediction_status": "predicted",
                "predicted_role": role, "confidence": distribution[role],
                "probabilities": dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0]))),
                "matches_target": target == role, "top_features": features,
                "feature_explanation_method": "matching_vocabulary",
                "target_benchmark_probability": distribution.get(target) if target else None,
                "note": "Model probabilities are not calibrated confidence or proof of career suitability. Matching vocabulary is not measured class contributions. No evaluated abstention threshold is available; mixed or unfamiliar profiles may be unreliable."}
    except Exception:
        logger.warning("ML role analysis unavailable.")
        return _no_prediction("unavailable", "ML model could not be loaded, trained or used; rule analysis remains available.")
