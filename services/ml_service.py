"""
DigiSafe - Machine Learning Detection Service
==============================================
Sections 3.3.6 and 3.12.3 - Machine Learning Text Classification Module.

Runtime inference wrapper around the two scikit-learn models trained by
ml_model/train_model.py:

    harassment_classifier.joblib  TF-IDF -> Multinomial Naive Bayes -> Platt
                                  calibration            (binary: abusive?)
    category_classifier.joblib    TF-IDF -> LinearSVC -> Platt calibration
                                  (multiclass: which kind of abuse?)

Both are loaded once, lazily, on first classification and then cached for the
lifetime of the process, so per-request inference stays well inside the
three-second submission budget set by the Performance non-functional
requirement (Section 3.10).

Implements Section 3.12.3 steps 2-8:
    2. Receive the submitted text evidence.
    3. Pre-process (lowercase, stop-word removal, NLTK tokenisation/stemming).
    4. Transform into TF-IDF feature vectors using Scikit-learn.
    5. Load the pre-trained Scikit-learn classification model.
    6. Predict the class label and compute the associated confidence score.
    7. If confidence >= threshold and label is abusive, flag for review.
    8. Otherwise mark the record as non-abusive.

Severity mapping
----------------
Section 3.3.6 requires a severity band (None / Low / Medium / High / Critical)
in addition to the binary label. Severity is driven primarily by WHAT KIND of
threat the message is, not by how confident the classifier is that it is
abusive: a death threat is severe because of what it is, and it would be wrong
to downgrade it to "Low" merely because the model was less certain.

The mapping is therefore:

  1. The category model gives a probability distribution over abuse types.
  2. Each category has a baseline severity (violence/blackmail -> Critical,
     stalking -> High, general harassment -> Medium).
  3. Severity is taken from the highest-severity category holding at least
     ESCALATION_MASS of the probability mass - not merely the single top-ranked
     category. This deliberately guards against the model's known confusion
     between Cyberstalking and Physical Violence (see metrics.json): a death
     threat ranked second behind stalking still escalates to Critical.
  4. The band is lowered by one level when the binary model is only marginally
     confident the message is abusive at all (below LOW_CONFIDENCE), so
     borderline cases are not over-reported to law enforcement.

This is documented, auditable policy applied on top of model output - not a
hidden second classifier. It is stated here because a severity band printed in
a court-admissible report must be explainable in court.
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict

from ml_model.preprocessing import preprocess_text  # noqa: F401  (re-exported)

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent / "ml_model"
BINARY_MODEL_PATH = MODEL_DIR / "harassment_classifier.joblib"
CATEGORY_MODEL_PATH = MODEL_DIR / "category_classifier.joblib"

MODEL_VERSION = "v2.0-tfidf-nb"

# Section 3.12.3 step 7: the decision threshold above which an "abusive"
# prediction is flagged for administrator review.
ABUSIVE_THRESHOLD = 0.50

# Baseline severity carried by each category of abuse.
CATEGORY_SEVERITY = {
    "Physical Violence / Life Threat": "Critical",
    "Blackmail / Non-Consensual Extortion": "Critical",
    "Cyberstalking / Intimidation": "High",
    "Severe Harassment / Defamation / Hate Speech": "Medium",
}

# A category is allowed to set the severity band if it holds at least this much
# of the category model's probability mass, even when it is not ranked first.
ESCALATION_MASS = 0.20

# Below this binary confidence the case is treated as borderline and the
# severity band is reduced by one level.
LOW_CONFIDENCE = 0.65

_SEVERITY_ORDER = ["None", "Low", "Medium", "High", "Critical"]

_models = {"binary": None, "category": None, "loaded": False}
_load_lock = threading.Lock()


def _load_models():
    """Load both joblib pipelines once, under a lock (thread-safe)."""
    if _models["loaded"]:
        return

    with _load_lock:
        if _models["loaded"]:
            return

        import joblib

        missing = [p.name for p in (BINARY_MODEL_PATH, CATEGORY_MODEL_PATH) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"Trained model file(s) not found: {', '.join(missing)}. "
                f"Run:  python ml_model/build_dataset.py && python ml_model/train_model.py"
            )

        try:
            _models["binary"] = joblib.load(BINARY_MODEL_PATH)
            _models["category"] = joblib.load(CATEGORY_MODEL_PATH)
        except Exception as exc:
            # Almost always a version drift: the pickles were produced by the
            # scikit-learn/numpy versions pinned in requirements.txt, and
            # something installed a different one. Say so plainly, because the
            # raw pickle error gives no hint about the cause.
            raise RuntimeError(
                f"Could not load the trained models ({type(exc).__name__}: {exc}). "
                "This usually means the installed scikit-learn/numpy differs from "
                "the versions pinned in requirements.txt that produced the .joblib "
                "files. Either reinstall the pinned versions, or retrain and "
                "re-commit the models with:  python ml_model/build_dataset.py && "
                "python ml_model/train_model.py"
            ) from exc

        _models["loaded"] = True
        logger.info("DigiSafe ML models loaded (%s)", MODEL_VERSION)


def warmup() -> bool:
    """Eagerly load the models at application start-up.

    Called from the FastAPI lifespan handler so that the first victim to
    submit evidence does not absorb the model-loading latency.
    """
    try:
        _load_models()
        return True
    except Exception:
        logger.exception("ML model warm-up failed")
        return False


def _rank(band: str) -> int:
    return _SEVERITY_ORDER.index(band)


def _demote(band: str) -> str:
    return _SEVERITY_ORDER[max(_rank(band) - 1, 1)]


def _severity_from_categories(category_probabilities):
    """Highest baseline severity among categories holding real probability mass."""
    band = "Low"
    for category, probability in category_probabilities.items():
        if probability < ESCALATION_MASS:
            continue
        candidate = CATEGORY_SEVERITY.get(category)
        if candidate and _rank(candidate) > _rank(band):
            band = candidate
    return band


def classify_text(text: str) -> Dict[str, Any]:
    """Classify a piece of evidence text.

    Returns the classification contract consumed by routers/evidence.py and
    services/report_service.py:

        label             "Abusive" | "Non-Abusive"
        confidence_score  float 0.0-1.0, the model's probability for the
                          predicted class
        threat_level      "None" | "Low" | "Medium" | "High" | "Critical"
        model_version     identifier persisted to the ML_CLASSIFICATION table
        detected_categories  list of predicted abuse category (empty if clean)
        risk_summary      human-readable line shown in the UI and PDF report
    """
    if not text or not text.strip():
        return {
            "label": "Non-Abusive",
            "confidence_score": 0.0,
            "threat_level": "None",
            "model_version": MODEL_VERSION,
            "detected_categories": [],
            "risk_summary": "No text content submitted for analysis.",
        }

    _load_models()

    # Steps 3-6: pre-process -> TF-IDF -> predict. The pre-processing and
    # vectorisation are inside the persisted Pipeline, so they are guaranteed
    # identical to what was applied during training.
    abusive_probability = float(_models["binary"].predict_proba([text])[0][1])
    is_abusive = abusive_probability >= ABUSIVE_THRESHOLD

    if not is_abusive:
        # Step 8: report confidence in the predicted (non-abusive) class.
        return {
            "label": "Non-Abusive",
            "confidence_score": round(1.0 - abusive_probability, 4),
            "threat_level": "None",
            "model_version": MODEL_VERSION,
            "detected_categories": [],
            "risk_summary": (
                "Content analysed by the TF-IDF/Naive Bayes classifier: no abusive, "
                "threatening, or harassing pattern detected."
            ),
        }

    # Step 7: flagged. Determine which category of abuse this is.
    category_model = _models["category"]
    probabilities = category_model.predict_proba([text])[0]
    category_probabilities = {
        str(name): float(p) for name, p in zip(category_model.classes_, probabilities)
    }

    abuse_probabilities = {
        name: p for name, p in category_probabilities.items() if name != "Non-Abusive"
    }
    category = max(abuse_probabilities, key=abuse_probabilities.get)
    category_confidence = abuse_probabilities[category]

    # Every abuse category holding meaningful probability mass is reported, so a
    # message that is both a threat and an extortion attempt surfaces as both.
    detected_categories = [
        name for name, p in sorted(
            abuse_probabilities.items(), key=lambda kv: kv[1], reverse=True
        )
        if p >= ESCALATION_MASS
    ] or [category]

    threat_level = _severity_from_categories(abuse_probabilities)
    if abusive_probability < LOW_CONFIDENCE:
        threat_level = _demote(threat_level)

    if threat_level == "Critical":
        summary = (
            f"CRITICAL THREAT DETECTED: classified as {category} "
            f"({abusive_probability:.0%} confidence). Immediate review required."
        )
    elif threat_level == "High":
        summary = (
            f"HIGH SEVERITY ABUSE: classified as {category} "
            f"({abusive_probability:.0%} confidence). Priority review recommended."
        )
    elif threat_level == "Medium":
        summary = (
            f"MEDIUM SEVERITY ABUSE: hostile or intimidating language consistent with "
            f"{category} ({abusive_probability:.0%} confidence)."
        )
    else:
        summary = (
            f"LOW SEVERITY: borderline abusive language detected "
            f"({abusive_probability:.0%} confidence). Manual review advised."
        )

    return {
        "label": "Abusive",
        "confidence_score": round(abusive_probability, 4),
        "threat_level": threat_level,
        "model_version": MODEL_VERSION,
        "detected_categories": detected_categories,
        "category_confidence": round(category_confidence, 4),
        "risk_summary": summary,
    }
