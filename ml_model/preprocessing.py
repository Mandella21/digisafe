"""
DigiSafe - NLTK Text Pre-processing
====================================
Section 3.12.3 (ML Text Classification Algorithm), steps 3-4:

    "Pre-process the text: convert to lowercase, remove stop-words, and
     tokenise using NLTK."

This module is imported by BOTH the training script (ml_model/train_model.py)
and the inference service (services/ml_service.py). Keeping a single shared
implementation guarantees that a message is processed identically at training
time and at prediction time - a mismatch between the two is the most common
cause of a model that scores well offline but behaves badly in production.

Deployment note
---------------
NLTK's `RegexpTokenizer` and `PorterStemmer` are pure-Python and require no
downloaded corpora, so they work on any host with no network access at
runtime. Only the stop-word list ships as downloadable data, so this module
tries NLTK's corpus first and falls back to an equivalent bundled list. The
fallback keeps the container start-up deterministic on free-tier hosting
where `nltk.download()` may be blocked or slow.
"""

from nltk.stem import PorterStemmer
from nltk.tokenize import RegexpTokenizer

# --- Stop-words -----------------------------------------------------------
# Try NLTK's corpus; fall back to the bundled copy of the same list if the
# corpus has not been downloaded on this host.
_FALLBACK_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself",
    "no", "nor", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she",
    "should", "so", "some", "such", "t", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "you", "your", "yours", "yourself", "yourselves",
}

# Negations and modals are deliberately KEPT even though standard stop-word
# lists remove them. "i will not hurt you" and "i will hurt you" must not
# collapse to the same token sequence in a harassment classifier.
_KEEP_ALWAYS = {
    "not", "no", "nor", "never", "will", "wont", "cant", "cannot", "should",
    "would", "must", "if", "or", "until", "unless", "you", "your", "i", "me",
}


def _load_stopwords():
    try:
        from nltk.corpus import stopwords

        words = set(stopwords.words("english"))
    except Exception:
        words = set(_FALLBACK_STOPWORDS)
    return words - _KEEP_ALWAYS


STOP_WORDS = _load_stopwords()

_tokenizer = RegexpTokenizer(r"[a-z0-9']+")
_stemmer = PorterStemmer()


def preprocess_text(text):
    """Lowercase, tokenise (NLTK), drop stop-words, and stem (NLTK Porter).

    Returns a list of processed tokens.
    """
    if not text:
        return []

    tokens = _tokenizer.tokenize(text.lower())
    return [
        _stemmer.stem(tok)
        for tok in tokens
        if tok not in STOP_WORDS and len(tok) > 1
    ]


def preprocess_to_string(text):
    """Pre-process and re-join to a string.

    This is the callable handed to scikit-learn's TfidfVectorizer as its
    `preprocessor`. It must be a module-level function (not a lambda or a
    closure) so that joblib can pickle the fitted pipeline.
    """
    return " ".join(preprocess_text(text))
