# DigiSafe — Machine Learning Detection Module

Reference documentation for the ML component (Objective 4; Sections 3.3.6, 3.12.3,
3.16 and 4.1 of the project report). Written so the figures and design decisions
here can be quoted directly in Chapter 4 and defended in the viva.

---

## 1. What the module does

Every piece of text evidence submitted to DigiSafe is classified synchronously
during the submission transaction (Section 3.8.2: *"The system shall invoke the
ML classification model synchronously during the evidence submission
workflow"*). The classifier returns:

| Field | Meaning |
|---|---|
| `label` | `Abusive` or `Non-Abusive` |
| `confidence_score` | Calibrated probability for the class actually predicted |
| `threat_level` | `None` / `Low` / `Medium` / `High` / `Critical` |
| `detected_categories` | Which kind(s) of abuse were detected |
| `model_version` | Written to the `ML_CLASSIFICATION` table for auditability |
| `risk_summary` | Plain-language line shown in the UI and the PDF report |

Evidence classified `High` or `Critical` is flagged, an `ALERT` row is raised for
the administrator/officer, and the action is written to the `AUDIT_LOG`.

---

## 2. Architecture

Two scikit-learn pipelines, both persisted with `joblib`:

**Binary classifier** — `ml_model/harassment_classifier.joblib`

```
NLTK pre-processing → TF-IDF (1–2 grams) → Multinomial Naive Bayes → Platt calibration
```

**Category classifier** — `ml_model/category_classifier.joblib`

```
NLTK pre-processing → TF-IDF (1–2 grams) → LinearSVC → Platt calibration
```

### Pre-processing (`ml_model/preprocessing.py`)

Implements Section 3.12.3 step 3 — lowercase, tokenise, remove stop-words, stem:

- NLTK `RegexpTokenizer` for tokenisation
- NLTK `PorterStemmer` for stemming (`threatening` → `threaten`)
- Stop-word removal, **with negations and modals deliberately retained**

That last point matters and is worth raising in the viva: standard stop-word
lists delete `not`, `no`, `never` and `will`. Without them, *"I will **not** hurt
you"* and *"I will hurt you"* reduce to the same token sequence. In a harassment
classifier that is not a tuning detail, it is a correctness bug.

The same module is imported by both the training script and the inference
service, so a message is processed identically at training and prediction time.

### Why two different algorithms

Naive Bayes is strong on the binary task. On the four-way category task it is
noticeably weaker than a discriminative model, because the abuse categories
share much of their vocabulary and NB's feature-independence assumption breaks
down. Measured on the same grouped hold-out:

| Category model | Accuracy | Macro-F1 |
|---|---|---|
| Multinomial Naive Bayes | 0.831 | 0.768 |
| **LinearSVC (calibrated)** | **0.857** | **0.786** |

### Why calibration

Raw Multinomial Naive Bayes is a well-known poor probability estimator — it is
systematically over-confident. Since `confidence_score` is displayed to victims
and printed into a document intended for court, the classifier is wrapped in
`CalibratedClassifierCV(method="sigmoid")` (Platt scaling). This also improved
accuracy from 0.9417 to 0.9595. Brier score on the full corpus: **0.0006**.

---

## 3. Training corpus

`ml_model/dataset/harassment_dataset.csv` — 2,520 rows, exactly balanced
(1,260 abusive / 1,260 non-abusive), built by `ml_model/build_dataset.py` from
154 hand-written seed messages expanded by template combination.

| Category | Rows |
|---|---|
| Physical Violence / Life Threat | 320 |
| Blackmail / Non-Consensual Extortion | 320 |
| Cyberstalking / Intimidation | 300 |
| Severe Harassment / Defamation / Hate Speech | 320 |
| Non-Abusive | 1,260 |

### Declare this honestly

**This is a curated synthetic corpus, not scraped real-world data.** Say so
plainly if asked. It is consistent with Section 6 of your proposal, which scopes
the project as a prototype *"developed and demonstrated within an academic
environment using sample and simulated data"*. Presenting these figures as
real-world harassment-detection accuracy would be a misrepresentation.

### Hard negatives

Roughly half the non-abusive rows are deliberately difficult: messages that are
angry, sad, or that *discuss* abuse without being abusive — *"our lecturer
discussed cyberbullying in class today"*, *"the news said a man was killed in an
accident"*, *"I am writing my project on detecting abusive messages"*. Without
these the model would collapse into keyword matching, and every crime-news
article a victim pasted in would be flagged as a death threat. `test_04c` in the
test suite locks this behaviour in.

---

## 4. Evaluation

### The split is grouped, and that is the important methodological point

Because rows are surface variants of shared seed sentences, a plain random split
would put variants of the *same* sentence in both train and test. The model
would be scored on sentences it had effectively already memorised and the
accuracy would be inflated and meaningless.

All evaluation therefore uses `GroupShuffleSplit` / `StratifiedGroupKFold`
**grouped on `seed_id`**, so every test sentence comes from a seed the model
never saw. If an examiner asks one hard question about your ML work, it will
probably be about leakage — this is your answer.

### Binary classification (held-out, 617 samples from 39 unseen seed groups)

| Metric | Value |
|---|---|
| Accuracy | **0.9595** |
| Precision (abusive) | 0.9335 |
| Recall (abusive) | **0.9904** |
| F1 (abusive) | 0.9611 |
| ROC-AUC | 0.9964 |

Confusion matrix:

|  | Predicted Non-Abusive | Predicted Abusive |
|---|---|---|
| **Actual Non-Abusive** | 283 (TN) | 22 (FP) |
| **Actual Abusive** | 3 (FN) | 309 (TP) |

**5-fold grouped cross-validation F1: 0.9698 ± 0.0127**
(folds: 0.9546, 0.9768, 0.9881, 0.9562, 0.9732)

### On the error trade-off

The model makes 22 false positives against only 3 false negatives. That
asymmetry is appropriate and defensible for this system: a false positive sends
a harmless message to a human reviewer who dismisses it, whereas a false
negative means a genuine threat is never escalated. In a victim-safety tool the
costs are not symmetric, so recall is the metric to optimise. Be ready to say
this — it shows you understand what the numbers mean, not just what they are.

### Category classification

Accuracy **0.857**, macro-F1 **0.786**.

Known weakness, and state it before you are asked: Cyberstalking and Physical
Violence are the two categories most often confused, because intimidation
phrasing such as *"I will find you"* or *"I am coming for you"* genuinely
occurs in both. This is real semantic overlap, not a training defect.

The system mitigates it rather than hiding it: severity escalates whenever a
high-risk category holds meaningful probability mass, not merely when it ranks
first — so a death threat ranked second behind stalking still escalates to
Critical.

---

## 5. Severity mapping

Severity is driven by **what kind of threat it is**, not by how confident the
classifier is that it is abusive. A death threat is severe because of what it
is; it would be wrong to downgrade it to "Low" merely because the model was less
certain.

| Category | Baseline severity |
|---|---|
| Physical Violence / Life Threat | Critical |
| Blackmail / Non-Consensual Extortion | Critical |
| Cyberstalking / Intimidation | High |
| Severe Harassment / Defamation / Hate Speech | Medium |

Then:
1. Severity is taken from the highest-severity category holding ≥ 20% of the
   probability mass (guards against the stalking/violence confusion above).
2. The band drops one level if binary confidence is below 0.65, so borderline
   cases are not over-reported to law enforcement.

This is documented, auditable policy applied on top of model output — not a
hidden second classifier. A severity band printed in a court document has to be
explainable in court, which is why it is written down here.

---

## 6. Reproducing the results

```bash
python ml_model/build_dataset.py
python ml_model/train_model.py
```

Fully deterministic (`random_state=42`) — it reproduces the figures above
exactly. Full metrics, including per-class breakdowns, are written to
`ml_model/metrics.json`.

Trained with scikit-learn 1.9.0 on Python 3.14.3. The deployment host retrains
from source rather than loading the committed `.joblib` files, so the artefacts
always match the installed library versions.

---

## 7. Honest limitations

State these yourself in the viva. Naming your own limitations is what
distinguishes an engineer from someone quoting a number off a screen.

1. **The corpus is synthetic.** Accuracy on a curated academic corpus is not
   real-world accuracy. Validating this properly needs an independently
   labelled dataset of genuine messages.
2. **English only.** No Twi, Ga, Ewe, Pidgin, or code-switched text — a real
   limitation for the Ghanaian context this system targets, and the single most
   valuable direction for future work.
3. **No sarcasm, irony, or context.** Each message is classified in isolation,
   with no conversation history and no sender/recipient relationship.
4. **Bag-of-words, not comprehension.** TF-IDF with bigrams captures short
   phrases, not meaning. Novel phrasing that shares no vocabulary with the
   training data will be missed.
5. **Adversaries adapt.** Deliberate obfuscation (`k1ll`, spacing, emoji
   substitution) would evade this model. The Maintainability requirement in
   Section 3.10 anticipates periodic retraining for exactly this reason.
6. **Classification is decision-support, not proof.** It carries no evidential
   weight and is not expert opinion evidence. The PDF report states this on its
   face. Crucially, the cryptographic integrity guarantee — which is what makes
   the evidence legally useful — is entirely independent of it and is unaffected
   by whether a classification is right.
