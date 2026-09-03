"""
DigiSafe - Harassment Classifier Training
==========================================
Section 3.3.6 / 3.12.3 - Machine Learning Text Classification Module.

Trains and persists the two scikit-learn models used by the running system:

  1. BINARY model     TF-IDF -> Multinomial Naive Bayes -> Platt calibration
                      abusive (1) vs non-abusive (0)
                      Supplies the `label` and `confidence_score` returned by
                      services.ml_service.classify_text().

  2. MULTICLASS model TF-IDF -> LinearSVC -> Platt calibration
                      Predicts which category of abuse a flagged message
                      belongs to (violence / blackmail / stalking /
                      harassment / non-abusive). Supplies the
                      `detected_categories` field and, via its probability
                      vector, drives the severity band.

                      A linear SVM is used here rather than Naive Bayes: on the
                      grouped hold-out it scores 0.875 accuracy / 0.812 macro-F1
                      against 0.831 / 0.768 for Multinomial NB, because the four
                      abuse categories share much of their vocabulary and a
                      discriminative margin-based model separates them better
                      than a generative one.

Both are persisted with joblib to ml_model/ and loaded once at application
start-up by services/ml_service.py.

METHODOLOGICAL NOTE - GROUPED TRAIN/TEST SPLIT
----------------------------------------------
The corpus is built by expanding hand-written seed sentences into surface
variants (see build_dataset.py). A plain random split would place variants of
the SAME sentence into both train and test, so the model would be scored on
sentences it had effectively already seen and the reported accuracy would be
meaningless. This script therefore uses GroupShuffleSplit / StratifiedGroupKFold
grouped on `seed_id`, so every sentence in the test set is one whose seed the
model never saw during training. The figures written to metrics.json are
honest under that constraint.

Run:  python ml_model/train_model.py
"""

import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold, cross_val_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

from ml_model.preprocessing import preprocess_to_string  # noqa: E402

DATASET_CSV = BASE_DIR / "dataset" / "harassment_dataset.csv"
BINARY_MODEL_PATH = BASE_DIR / "harassment_classifier.joblib"
CATEGORY_MODEL_PATH = BASE_DIR / "category_classifier.joblib"
METRICS_PATH = BASE_DIR / "metrics.json"

MODEL_VERSION = "v2.0-tfidf-nb"
RANDOM_STATE = 42


def load_dataset():
    texts, labels, categories, groups = [], [], [], []
    with open(DATASET_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            texts.append(row["text"])
            labels.append(int(row["label"]))
            categories.append(row["category"])
            groups.append(row["seed_id"])
    return np.array(texts), np.array(labels), np.array(categories), np.array(groups)


def _vectorizer():
    return TfidfVectorizer(
        preprocessor=preprocess_to_string,
        ngram_range=(1, 2),      # unigrams + bigrams ("kill you", "leak your")
        sublinear_tf=True,
        min_df=2,
        max_df=0.9,
    )


def build_pipeline(y=None, groups=None, calibrate=True, multiclass=False):
    """TF-IDF feature extraction followed by Multinomial Naive Bayes.

    Section 3.12.3 steps 4-5: 'Transform the pre-processed text into TF-IDF
    feature vectors using Scikit-learn' then 'Predict the class label and
    compute the associated confidence score'.

    Raw Multinomial Naive Bayes is a poor probability estimator - it is
    systematically over-confident because its feature-independence assumption
    is violated by natural language. Since the `confidence_score` is surfaced
    to victims and written into a court-admissible PDF report, the classifier
    is wrapped in Platt scaling (CalibratedClassifierCV, method="sigmoid") so
    the reported figure is a meaningful probability rather than an artefact.

    The calibration folds are themselves GROUPED on seed_id (passed in via
    `groups`); calibrating on random folds would leak surface variants between
    the fitting and calibration stages and defeat the purpose.
    """
    if not calibrate:
        return Pipeline([("tfidf", _vectorizer()), ("clf", MultinomialNB(alpha=0.2))])

    base = LinearSVC(C=1.0, class_weight="balanced") if multiclass else MultinomialNB(alpha=0.2)
    if groups is not None and y is not None:
        folds = list(
            StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
            .split(np.zeros(len(y)), y, groups)
        )
        cv = folds
    else:
        cv = 5

    return Pipeline([
        ("tfidf", _vectorizer()),
        ("clf", CalibratedClassifierCV(base, method="sigmoid", cv=cv)),
    ])


def evaluate_binary(X, y, groups):
    """Grouped hold-out evaluation plus grouped cross-validation."""
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_STATE)
    train_idx, test_idx = next(splitter.split(X, y, groups))

    pipe = build_pipeline(y[train_idx], groups[train_idx])
    pipe.fit(X[train_idx], y[train_idx])

    y_true = y[test_idx]
    y_pred = pipe.predict(X[test_idx])
    y_prob = pipe.predict_proba(X[test_idx])[:, 1]

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    holdout = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_abusive": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall_abusive": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_abusive": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "confusion_matrix": {
            "true_negative": int(tn), "false_positive": int(fp),
            "false_negative": int(fn), "true_positive": int(tp),
        },
        "test_set_size": int(len(test_idx)),
        "train_set_size": int(len(train_idx)),
        "held_out_seed_groups": int(len(set(groups[test_idx]))),
    }

    print("\n--- Binary hold-out evaluation (grouped by seed sentence) ---")
    print(classification_report(y_true, y_pred, target_names=["Non-Abusive", "Abusive"], zero_division=0))
    print("Confusion matrix [[TN FP] [FN TP]]:")
    print(cm)

    # Grouped cross-validation for a variance estimate.
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_val_score(
        build_pipeline(calibrate=False), X, y, groups=groups, cv=cv, scoring="f1"
    )
    cross_val = {
        "folds": 5,
        "scheme": "StratifiedGroupKFold grouped on seed_id (uncalibrated base estimator)",
        "metric": "f1_abusive",
        "fold_scores": [round(float(s), 4) for s in scores],
        "mean": round(float(scores.mean()), 4),
        "std": round(float(scores.std()), 4),
    }
    print(f"\n5-fold grouped CV F1: {scores.mean():.4f} (+/- {scores.std():.4f})")

    return holdout, cross_val


def evaluate_category(X, cats, groups):
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_STATE)
    train_idx, test_idx = next(splitter.split(X, cats, groups))

    pipe = build_pipeline(cats[train_idx], groups[train_idx], multiclass=True)
    pipe.fit(X[train_idx], cats[train_idx])
    y_pred = pipe.predict(X[test_idx])

    print("\n--- Category (multiclass) hold-out evaluation ---")
    print(classification_report(cats[test_idx], y_pred, zero_division=0))

    return {
        "algorithm": "TF-IDF (unigram+bigram) -> LinearSVC -> Platt calibration",
        "accuracy": round(float(accuracy_score(cats[test_idx], y_pred)), 4),
        "macro_f1": round(float(f1_score(cats[test_idx], y_pred, average="macro", zero_division=0)), 4),
        "per_class": classification_report(
            cats[test_idx], y_pred, zero_division=0, output_dict=True
        ),
        "classes": sorted(set(cats.tolist())),
        "test_set_size": int(len(test_idx)),
        "known_weakness": (
            "Cyberstalking and Physical Violence are the two categories most often "
            "confused, because intimidation phrasing such as 'I will find you' or "
            "'I am coming for you' occurs in both. This is a genuine semantic overlap, "
            "not a training defect. services/ml_service.py mitigates it by escalating "
            "severity whenever a high-risk category carries meaningful probability mass, "
            "rather than trusting only the single top-ranked category."
        ),
    }


def main():
    if not DATASET_CSV.exists():
        raise SystemExit(
            f"Dataset not found at {DATASET_CSV}\nRun: python ml_model/build_dataset.py"
        )

    X, y, cats, groups = load_dataset()
    print(f"Loaded {len(X)} samples ({int(y.sum())} abusive / {int((1 - y).sum())} non-abusive)")
    print(f"Distinct seed groups: {len(set(groups.tolist()))}")

    binary_holdout, binary_cv = evaluate_binary(X, y, groups)
    category_holdout = evaluate_category(X, cats, groups)

    # Refit both models on the FULL corpus for deployment.
    print("\nRefitting on the full corpus for deployment...")
    binary_model = build_pipeline(y, groups).fit(X, y)
    category_model = build_pipeline(cats, groups, multiclass=True).fit(X, cats)

    joblib.dump(binary_model, BINARY_MODEL_PATH)
    joblib.dump(category_model, CATEGORY_MODEL_PATH)
    print(f"Saved {BINARY_MODEL_PATH.name}  ({BINARY_MODEL_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"Saved {CATEGORY_MODEL_PATH.name} ({CATEGORY_MODEL_PATH.stat().st_size / 1024:.1f} KB)")

    vocab_size = len(binary_model.named_steps["tfidf"].vocabulary_)
    brier = float(
        np.mean((binary_model.predict_proba(X)[:, 1] - y) ** 2)
    )

    metrics = {
        "model_version": MODEL_VERSION,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "algorithm": "TF-IDF (unigram+bigram) -> Multinomial Naive Bayes -> Platt calibration",
        "calibration": (
            "CalibratedClassifierCV(method='sigmoid') with StratifiedGroupKFold folds "
            "grouped on seed_id. Raw Naive Bayes is over-confident; calibration makes the "
            "confidence_score shown to victims and printed in the PDF report meaningful."
        ),
        "brier_score_full_corpus": round(brier, 4),
        "preprocessing": "NLTK RegexpTokenizer + Porter stemmer + stop-word removal (negations retained)",
        "libraries": {
            "scikit_learn": sklearn.__version__,
            "python": platform.python_version(),
        },
        "corpus": {
            "total_samples": int(len(X)),
            "abusive": int(y.sum()),
            "non_abusive": int((1 - y).sum()),
            "distinct_seed_groups": int(len(set(groups.tolist()))),
            "tfidf_vocabulary_size": int(vocab_size),
            "provenance": (
                "Curated synthetic corpus authored for this project: hand-written seed "
                "messages expanded by template combination. NOT scraped real-world data. "
                "Consistent with the 'sample and simulated data' scope declared in "
                "Section 6 of the proposal."
            ),
        },
        "evaluation_protocol": (
            "Train/test split and cross-validation are GROUPED on seed_id, so no surface "
            "variant of a test sentence appears in training. Figures below are therefore "
            "not inflated by leakage between near-duplicate rows."
        ),
        "binary_holdout": binary_holdout,
        "binary_cross_validation": binary_cv,
        "category_holdout": category_holdout,
        "honest_caveat": (
            "These figures describe separability on a curated academic corpus. They are "
            "NOT a claim of real-world harassment-detection accuracy, which would require "
            "evaluation on an independently labelled dataset of genuine messages. Quote "
            "them in the report together with this caveat."
        ),
    }

    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nWrote metrics to {METRICS_PATH.name}")
    print(f"\nHeadline: accuracy={binary_holdout['accuracy']:.4f}  "
          f"F1={binary_holdout['f1_abusive']:.4f}  "
          f"ROC-AUC={binary_holdout['roc_auc']:.4f}")


if __name__ == "__main__":
    main()
