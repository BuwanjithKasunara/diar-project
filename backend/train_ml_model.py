"""
Stand-alone Machine Learning Training & Evaluation Script
----------------------------------------------------------
Trains the DIAR Career Role Classification model on `career_profiles_dataset.csv`,
evaluates performance using stratified cross-validation and a train/test split,
prints a detailed classification report and confusion matrix, and saves the trained model.

Usage:
    cd backend
    python train_ml_model.py
"""
import os
import sys
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import pickle
try:
    import joblib
except ImportError:
    joblib = None

# Add app directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from app.modules import ml_classifier

def main():
    print("=" * 60)
    print("DIAR - Career Role Classification Model Training")
    print("=" * 60)

    dataset_path = os.path.join(current_dir, "app", "data", "career_profiles_dataset.csv")
    model_output_path = os.path.join(current_dir, "app", "data", "career_classifier.joblib")

    print(f"\n1. Loading dataset from: {dataset_path}")
    texts, labels = ml_classifier.load_dataset(dataset_path)
    print(f"   Loaded {len(texts)} samples across {len(set(labels))} classes:")
    from collections import Counter
    counts = Counter(labels)
    for role, count in sorted(counts.items()):
        print(f"   - {role:20s}: {count} samples")

    print("\n2. Splitting into Train (80%) and Test (20%) sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    print(f"   Train samples: {len(X_train)}, Test samples: {len(X_test)}")

    print("\n3. Building ML Pipeline (TF-IDF Vectorizer + Multinomial Logistic Regression)...")
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

    print("\n4. Performing 5-Fold Stratified Cross-Validation...")
    cv_scores = cross_val_score(pipeline, texts, labels, cv=5)
    print(f"   Cross-Validation Accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std():.2%})")

    print("\n5. Fitting model on training split and evaluating on hold-out test set...")
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"   Hold-out Test Accuracy: {acc:.2%}\n")

    print("Classification Report:")
    print("-" * 60)
    print(classification_report(y_test, y_pred, zero_division=0))

    print("\n6. Retraining final model on the entire dataset for production deployment...")
    final_pipeline = Pipeline([
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
    final_pipeline.fit(texts, labels)

    print(f"7. Saving model artifact to: {model_output_path}")
    if joblib is not None:
        joblib.dump(final_pipeline, model_output_path)
    else:
        with open(model_output_path, "wb") as f:
            pickle.dump(final_pipeline, f)
    print("   [SUCCESS] Model successfully trained and saved!")

    # Quick test inference
    print("\n8. Quick Sample Inference Test:")
    sample_text = (
        "Experienced engineer in machine learning, PyTorch, deep learning, "
        "and deploying computer vision models with Docker and FastAPI."
    )
    test_pred = ml_classifier.predict_role(sample_text, target_benchmark="AI Engineer")
    print(f"   Input snippet: '{sample_text}'")
    print(f"   Predicted Role: {test_pred['predicted_role']} (Confidence: {test_pred['confidence']:.2%})")
    print("   Probabilities breakdown:")
    for role, p in test_pred["probabilities"].items():
        print(f"     - {role:20s}: {p:.2%}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
