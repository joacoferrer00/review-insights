# Multi-Mention Classification — Acceptance Fixtures

These 5 cases are the acceptance test for the new prompt.
Run them manually before re-classifying the full dataset.
If all 5 pass, the prompt is ready. If not, iterate the prompt first.

A case "passes" when the model output (after Pydantic parsing) matches:
- correct number of mentions
- correct `main_topic` per mention
- `sentiment` within expected values
- `text_reference` is a literal substring (or near-literal) of `clean_text`
- no duplicate `main_topic` across mentions of the same review

---

## Case 1 — Single-topic positive (expected: 1 mention)

**Rationale:** The review praises only food quality with multiple adjectives ("tierno",
"al punto", "fresco"). Three adjectives about the same topic = one mention, not three.
This tests anti-over-segmentation.

**clean_text:**
```
El tiradito de salmón soberbio y fresco. La costilla a la leña tierna, al punto justo.
Sin dudas la mejor cocina que probé en Córdoba.
```

**Expected output:**
```json
{
  "mentions": [
    {
      "main_topic": "Food Quality",
      "sentiment": "positive",
      "urgency": "low",
      "is_actionable": false,
      "text_reference": "El tiradito de salmón soberbio y fresco. La costilla a la leña tierna, al punto justo.",
      "classification_confidence": 0.95
    }
  ]
}
```

---

## Case 2 — Single-topic negative (expected: 1 mention)

**Rationale:** Pure complaint about wait time. No other topic is mentioned.
Tests that the model picks `Service Speed` (not `Staff Attitude`) and marks it high urgency + actionable.

**clean_text:**
```
Tardamos más de una hora en que nos tomaran el pedido. El local estaba casi vacío
pero los mozos desaparecían constantemente. Inaceptable para un lugar de este nivel.
```

**Expected output:**
```json
{
  "mentions": [
    {
      "main_topic": "Service Speed",
      "sentiment": "negative",
      "urgency": "high",
      "is_actionable": true,
      "text_reference": "Tardamos más de una hora en que nos tomaran el pedido.",
      "classification_confidence": 0.95
    }
  ]
}
```

---

## Case 3 — Multi-topic, 2 topics (positive + negative) (expected: 2 mentions)

**Rationale:** The review clearly praises food and clearly criticizes ambiance (noise, table spacing).
Two distinct topics with opposite sentiments. Tests that the model splits correctly
and doesn't collapse everything into `Overall Experience`.

**clean_text:**
```
La comida estuvo espectacular, el bife de chorizo al punto justo y la entrada de burrata increíble.
Lástima que el ambiente deja mucho que desear: música a volumen altísimo que no dejaba conversar
y mesas muy juntas. Para la próxima piden turno para algo más tranquilo.
```

**Expected output:**
```json
{
  "mentions": [
    {
      "main_topic": "Food Quality",
      "sentiment": "positive",
      "urgency": "low",
      "is_actionable": false,
      "text_reference": "el bife de chorizo al punto justo y la entrada de burrata increíble",
      "classification_confidence": 0.92
    },
    {
      "main_topic": "Ambiance",
      "sentiment": "negative",
      "urgency": "medium",
      "is_actionable": true,
      "text_reference": "música a volumen altísimo que no dejaba conversar y mesas muy juntas",
      "classification_confidence": 0.9
    }
  ]
}
```

---

## Case 4 — Multi-topic, 3 topics (expected: 3 mentions, tests the cap)

**Rationale:** The review explicitly praises ambiance, staff, and food — three distinct topics.
Tests that the model correctly identifies all three and does NOT add a fourth
(`Overall Experience` on top). Cap = 3 distinct topics.

**clean_text:**
```
Increíble experiencia. La ambientación es hermosa, luz tenue y decoración con mucho detalle.
Los mozos fueron súper atentos, siempre pendientes sin ser invasivos.
Y la comida a la altura: el tiradito de salmón y la costilla a la leña son un must.
Volvería sin dudarlo.
```

**Expected output:**
```json
{
  "mentions": [
    {
      "main_topic": "Ambiance",
      "sentiment": "positive",
      "urgency": "low",
      "is_actionable": false,
      "text_reference": "La ambientación es hermosa, luz tenue y decoración con mucho detalle.",
      "classification_confidence": 0.93
    },
    {
      "main_topic": "Staff Attitude",
      "sentiment": "positive",
      "urgency": "low",
      "is_actionable": false,
      "text_reference": "Los mozos fueron súper atentos, siempre pendientes sin ser invasivos.",
      "classification_confidence": 0.95
    },
    {
      "main_topic": "Food Quality",
      "sentiment": "positive",
      "urgency": "low",
      "is_actionable": false,
      "text_reference": "el tiradito de salmón y la costilla a la leña son un must",
      "classification_confidence": 0.93
    }
  ]
}
```

---

## Case 5 — Same topic, mixed opinion (expected: 1 mention, neutral or negative)

**Rationale:** The review has a positive opinion about main courses and a negative opinion
about desserts — both about `Food Quality`. One topic, two directions.
The model must produce a **single mention** with `neutral` or the dominant sentiment (`negative`
is acceptable if the model weights the explicit disappointment more heavily).
This is NOT two mentions. Tests the "same topic → one mention" rule.

**clean_text:**
```
La carne estuvo excelente, tierna y al punto perfecto. Pero el postre fue una decepción total:
el tiramisú llegó frío y sin sabor. No entiendo cómo pueden fallar tanto en los postres
siendo tan buenos en lo demás.
```

**Expected output:**
```json
{
  "mentions": [
    {
      "main_topic": "Food Quality",
      "sentiment": "neutral",
      "urgency": "medium",
      "is_actionable": true,
      "text_reference": "el postre fue una decepción total: el tiramisú llegó frío y sin sabor",
      "classification_confidence": 0.85
    }
  ]
}
```

**Acceptable variants:**
- `sentiment: "negative"` is also valid (model weights the explicit complaint more)
- `text_reference` can span both the positive and negative fragments
- Must be exactly 1 mention with `main_topic: "Food Quality"`
