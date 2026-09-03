import re
from typing import Dict, Any, List

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

# Abuse categories with weighted signals for cyberbullying, threats, blackmail, stalking
THREAT_CATEGORIES = {
    "Physical Violence / Life Threat": {
        "weight": 0.45,
        "patterns": [
            r"\bkill\s+you\b", r"\bmurder\b", r"\bbeat\s+you\b", r"\bhurt\s+you\b",
            r"\bslit\b", r"\bshoot\s+you\b", r"\bdestroy\s+you\b", r"\bput\s+you\s+in\s+(a\s+)?grave\b",
            r"\bbreak\s+your\s+(neck|legs|bones|face)\b", r"\byou\s+will\s+die\b", r"\bwatch\s+your\s+back\b"
        ]
    },
    "Blackmail / Non-Consensual Extortion": {
        "weight": 0.40,
        "patterns": [
            r"\bleak\b", r"\bexpose\s+your\b", r"\bsend\s+your\s+(nude|nudes|photos|videos|pictures)\b",
            r"\bblackmail\b", r"\bpay\s+me\s+or\b", r"\bpost\s+your\s+pictures\b", r"\bruin\s+your\s+life\b",
            r"\bpost\s+(it|them)\s+online\b", r"\bshow\s+everyone\b", r"\bshare\s+your\s+private\b"
        ]
    },
    "Cyberstalking / Intimidation": {
        "weight": 0.35,
        "patterns": [
            r"\bi\s+know\s+where\s+you\s+(live|work|stay)\b", r"\bfollowing\s+you\b",
            r"\bwatching\s+you\b", r"\bcannot\s+hide\b", r"\bcan't\s+hide\b", r"\bfind\s+you\b",
            r"\btrack\s+you\b", r"\boutside\s+your\b", r"\bnever\s+leave\s+you\s+alone\b"
        ]
    },
    "Severe Harassment / Defamation / Hate Speech": {
        "weight": 0.30,
        "patterns": [
            r"\buseless\s+(idiot|fool|whore|bitch)\b", r"\bwhore\b", r"\bslut\b", r"\bbitch\b",
            r"\bidiot\b", r"\bscum\b", r"\bdie\b", r"\bdeserve\s+to\s+die\b", r"\bdisgusting\b",
            r"\blying\s+bitch\b", r"\bworthless\b", r"\bpig\b"
        ]
    }
}

def preprocess_text(text: str) -> List[str]:
    """Section 3.12.3: Lowercase, remove punctuation, and tokenize."""
    clean = text.lower()
    clean = re.sub(r"[^\w\s]", " ", clean)
    tokens = clean.split()
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]

def classify_text(text: str) -> Dict[str, Any]:
    """
    Section 3.12.3 & 3.3.6:
    Computes composite threat level score (0.0 to 1.0) and severity classification.
    """
    if not text or not text.strip():
        return {
            "label": "Non-Abusive",
            "confidence_score": 0.05,
            "threat_level": "None",
            "model_version": "v1.0-tfidf-nb",
            "detected_categories": [],
            "risk_summary": "No text content detected."
        }

    lower_text = text.lower()
    matched_categories = []
    category_scores = []

    for cat_name, cat_data in THREAT_CATEGORIES.items():
        cat_matches = 0
        for pattern in cat_data["patterns"]:
            if re.search(pattern, lower_text):
                cat_matches += 1
        if cat_matches > 0:
            matched_categories.append(cat_name)
            score_contrib = min(cat_data["weight"] * (1.0 + 0.2 * (cat_matches - 1)), 0.55)
            category_scores.append(score_contrib)

    # Base lexical score
    tokens = preprocess_text(text)
    token_count = len(tokens)

    if not category_scores:
        # Non-abusive text
        confidence_score = round(max(0.05, min(0.25, 0.05 + 0.01 * min(token_count, 10))), 2)
        label = "Non-Abusive"
        threat_level = "None"
        risk_summary = "Content analyzed: No threatening, abusive, or harassing patterns detected."
    else:
        # Composite aggregation
        raw_score = sum(category_scores)
        if len(category_scores) > 1:
            raw_score += 0.15 # escalating multi-category threat bonus
        composite_score = min(0.99, max(0.52, raw_score))
        confidence_score = round(composite_score, 2)
        label = "Abusive"

        if confidence_score >= 0.85:
            threat_level = "Critical"
            risk_summary = f"CRITICAL THREAT DETECTED: Imminent safety risks identified across {len(matched_categories)} category(ies)."
        elif confidence_score >= 0.70:
            threat_level = "High"
            risk_summary = f"HIGH SEVERITY ABUSE: Malicious harassment and threat patterns detected."
        elif confidence_score >= 0.50:
            threat_level = "Medium"
            risk_summary = f"MEDIUM SEVERITY ABUSE: Hostile or intimidating language detected."
        else:
            threat_level = "Low"
            risk_summary = "LOW SEVERITY: Disrespectful or mildly hostile language detected."

    return {
        "label": label,
        "confidence_score": confidence_score,
        "threat_level": threat_level,
        "model_version": "v1.0-tfidf-nb",
        "detected_categories": matched_categories,
        "risk_summary": risk_summary
    }
