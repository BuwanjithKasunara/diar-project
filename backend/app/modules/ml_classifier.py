"""
Machine Learning Role Classification Module
-------------------------------------------
Uses Natural Language Processing (TF-IDF Vectorization) and a calibrated
Supervised Machine Learning Classifier (Logistic Regression / Multinomial Softmax)
trained on a benchmark dataset of professional profiles and resumes.

Given a user's consolidated profile text, this module:
1. Predicts the closest benchmark professional identity (AI Engineer, Data Scientist,
   Software Engineer, Researcher, Entrepreneur).
2. Computes the prediction confidence score and probability distribution across all roles.
3. Identifies the primary keywords/features driving the prediction.
"""
import os
import csv
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATASET_PATH = os.path.join(DATA_DIR, "career_profiles_dataset.csv")
MODEL_PATH = os.path.join(DATA_DIR, "career_classifier.joblib")

_MODEL_PIPELINE = None


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


def predict_role(text: str, target_benchmark: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyzes profile/resume text with the ML model and returns:
    - predicted_role
    - confidence (0.0 to 1.0)
    - probabilities for all classes
    - matches_target (boolean comparing prediction to target_benchmark)
    - top_features (indicative words found in the text)
    """
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return {
            "model_available": True,
            "predicted_role": "Undetermined",
            "confidence": 0.0,
            "probabilities": {},
            "matches_target": False,
            "top_features": [],
            "note": "No text provided for Machine Learning role analysis."
        }

    model = get_model()
    if model is None:
        return {
            "model_available": False,
            "predicted_role": "Unavailable",
            "confidence": 0.0,
            "probabilities": {},
            "matches_target": False,
            "top_features": [],
            "note": "Machine Learning model is not loaded (scikit-learn required)."
        }

    classes = list(model.classes_)
    probs = model.predict_proba([cleaned_text])[0]
    prob_dict = {cls_name: round(float(prob), 4) for cls_name, prob in zip(classes, probs)}
    # Sort probabilities descending
    sorted_probs = dict(sorted(prob_dict.items(), key=lambda item: item[1], reverse=True))

    predicted_role = model.predict([cleaned_text])[0]
    confidence = round(float(max(probs)), 4)

    # Extract top keywords from the text that match the vectorizer vocabulary
    top_features = []
    try:
        vectorizer = model.named_steps["tfidf"]
        feature_names = set(vectorizer.get_feature_names_out())
        words_in_text = [w.lower() for w in cleaned_text.split() if len(w) > 2]
        matched_tokens = [w for w in set(words_in_text) if w in feature_names]
        top_features = matched_tokens[:8]
    except Exception:
        top_features = []

    matches_target = bool(target_benchmark and target_benchmark.lower() == predicted_role.lower())

    return {
        "model_available": True,
        "predicted_role": predicted_role,
        "confidence": confidence,
        "probabilities": sorted_probs,
        "matches_target": matches_target,
        "top_features": top_features,
        "target_benchmark_probability": sorted_probs.get(target_benchmark, 0.0) if target_benchmark else None,
    }
