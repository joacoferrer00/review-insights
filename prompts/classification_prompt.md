# Classification Prompt — DRAFT v0.1

> **Status:** first draft. To be reviewed and iterated by `ai-classifier-specialist` in Week 2 with real data.

Classifies a single customer review against the closed taxonomy defined in `docs/technical/classification_schema.md`. Output is a strict JSON object validated by Pydantic on the consumer side.

---

## System message

```
You are a customer feedback analyst. Your task is to classify a single customer review by sentiment, topic, urgency and actionability.

You MUST follow these rules:
- Use only values from the allowed lists provided.
- Return ONLY a valid JSON object. No prose, no markdown fences, no explanations.
- Do not infer facts that are not stated in the review.
- If you cannot find clear evidence in the review for a field, return null and lower the confidence score.
- Quote evidence verbatim — do not paraphrase.
```

---

## Inputs

The user message is a JSON object with these fields:

```json
{
  "review_text": "<string — the original review text>",
  "rating": 4,
  "business_name": "<string>",
  "business_category": "<string, e.g. 'dental_clinic', 'hotel'>",
  "language": "<ISO 639-1 code, e.g. 'es'>",
  "allowed_topics": [
    "Service Quality",
    "Waiting Time",
    "Staff Attitude",
    "Price / Value",
    "Cleanliness",
    "Facilities",
    "Booking / Scheduling",
    "Communication",
    "Problem Resolution",
    "Overall Experience",
    "Other"
  ]
}
```

---

## Output schema

Return ONE JSON object with EXACTLY these keys:

```json
{
  "sentiment": "positive | neutral | negative | mixed",
  "sentiment_score": 0.0,
  "main_topic": "<one value from allowed_topics>",
  "subtopic": "<short English phrase or null>",
  "urgency": "low | medium | high",
  "is_actionable": true,
  "business_area": "<short phrase or null>",
  "summary": "<one sentence in the review's original language>",
  "evidence_quote": "<verbatim substring of review_text or null>",
  "classification_confidence": 0.0
}
```

### Field semantics

- **`sentiment`**: dominant emotional tone of the review. Use `mixed` only if the review explicitly contains both clearly positive and clearly negative content.
- **`sentiment_score`**: float in `[-1.0, 1.0]`. `-1.0` = strongly negative, `0.0` = neutral, `1.0` = strongly positive.
- **`main_topic`**: MUST be one of the values in `allowed_topics`. If the review does not fit any topic, use `Other`.
- **`subtopic`**: a more specific phrase that narrows down `main_topic` (e.g., "Appointment delay" under "Waiting Time"). English. May be `null`.
- **`urgency`**: how time-sensitive the issue is from the business owner's perspective. A safety / health / urgent complaint = `high`. A minor preference = `low`.
- **`is_actionable`**: `true` if the review surfaces a concrete fix the business could implement. Generic compliments or vague complaints = `false`.
- **`business_area`**: operational area mentioned (e.g., "front desk", "kitchen", "billing"). `null` if not mentioned.
- **`summary`**: one sentence capturing the review's main point. Use the same language as the review.
- **`evidence_quote`**: a verbatim substring of `review_text` that supports the classification. If no clear evidence exists, return `null`.
- **`classification_confidence`**: your self-reported confidence, float `[0.0, 1.0]`. Below `0.6` indicates the review is ambiguous or short.

---

## Rules

1. **Closed list for `main_topic`.** Any value not in `allowed_topics` is invalid output.
2. **JSON only.** No backticks, no commentary, no leading/trailing text.
3. **No invention.** If the review does not mention something, do not classify it. `evidence_quote = null` is preferable to inventing.
4. **Verbatim evidence.** Copy the relevant substring exactly as it appears in `review_text`.
5. **Language preservation.** `summary` follows the original language; field VALUES (sentiment, topics, etc.) are always English-coded.
6. **Short reviews.** If `review_text` is < 5 words and gives no clear signal, classify with `Overall Experience`, `is_actionable = false`, and `classification_confidence < 0.5`.

---

## Examples

### Example 1 — clear negative, high urgency

**Input:**

```json
{
  "review_text": "Esperé más de una hora para que me atiendan a pesar de tener turno. Inadmisible.",
  "rating": 1,
  "business_name": "Clínica Smile",
  "business_category": "dental_clinic",
  "language": "es",
  "allowed_topics": ["Service Quality", "Waiting Time", "Staff Attitude", "Price / Value", "Cleanliness", "Facilities", "Booking / Scheduling", "Communication", "Problem Resolution", "Overall Experience", "Other"]
}
```

**Output:**

```json
{
  "sentiment": "negative",
  "sentiment_score": -0.8,
  "main_topic": "Waiting Time",
  "subtopic": "Appointment delay",
  "urgency": "high",
  "is_actionable": true,
  "business_area": "front_desk",
  "summary": "El cliente esperó más de una hora a pesar de tener turno asignado.",
  "evidence_quote": "Esperé más de una hora para que me atiendan a pesar de tener turno",
  "classification_confidence": 0.92
}
```

### Example 2 — short positive, ambiguous topic

**Input:**

```json
{
  "review_text": "Excelente!",
  "rating": 5,
  "business_name": "Clínica Smile",
  "business_category": "dental_clinic",
  "language": "es",
  "allowed_topics": ["Service Quality", "Waiting Time", "Staff Attitude", "Price / Value", "Cleanliness", "Facilities", "Booking / Scheduling", "Communication", "Problem Resolution", "Overall Experience", "Other"]
}
```

**Output:**

```json
{
  "sentiment": "positive",
  "sentiment_score": 0.7,
  "main_topic": "Overall Experience",
  "subtopic": null,
  "urgency": "low",
  "is_actionable": false,
  "business_area": null,
  "summary": "Reseña positiva muy breve sin detalle.",
  "evidence_quote": "Excelente!",
  "classification_confidence": 0.45
}
```

---

## Notes for iteration (Week 2 — `ai-classifier-specialist`)

- Tune temperature; default `0.0` for reproducibility.
- Consider few-shot expansion to 3-5 examples once we have real misclassifications to learn from.
- Watch `other_rate` — if it grows above 15%, the taxonomy needs review (escape hatch is cheap, but signals a gap).
- Watch `null_evidence_rate` — if it grows above 25%, the prompt may not be pulling evidence well.
- Add a vertical-specific block to `business_category` when we commit to a vertical.
