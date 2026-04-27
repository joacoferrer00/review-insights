# Insight Generation Prompt — DRAFT v0.1

> **Status:** first draft. To be reviewed and iterated by `ai-classifier-specialist` and `business-writer` in Week 2 with real data.

Takes aggregated metrics and representative quotes for a single business and produces a prioritized list of insights. The output feeds the `insights` canonical table (see `docs/technical/data_contract.md`) and is consumed by `executive_summary_prompt.md` downstream.

> **Critical rule:** the LLM does NOT see raw reviews here. It receives **aggregated metrics + curated quotes** and must work only from that. Counts and rankings are computed in Python — the LLM never does math.

---

## System message

```
You are a customer experience analyst writing insights for a business owner.

You receive aggregated metrics and selected quotes for a single business. Your job is to produce a prioritized list of insights that the owner can act on.

You MUST follow these rules:
- Use ONLY the metrics and quotes provided. Do not invent numbers, percentages, or facts.
- Each insight must include verbatim evidence — a quote from the input.
- Recommendations must be specific and operational, not generic platitudes.
- Return ONLY a valid JSON array. No prose, no markdown fences.
- Write `title`, `description` and `recommendation` in Spanish (the report goes to a Spanish-speaking business owner).
- Keep `insight_type` and `priority` in the controlled vocabulary.
```

---

## Inputs

The user message is a JSON object with this structure:

```json
{
  "business_name": "<string>",
  "business_category": "<string>",
  "period": "<e.g. '2026-01 to 2026-04' or 'all_time'>",
  "total_reviews": 312,
  "avg_rating": 3.8,
  "sentiment_distribution": {
    "positive": 0.55,
    "neutral": 0.18,
    "negative": 0.27
  },
  "top_negative_topics": [
    {
      "main_topic": "Waiting Time",
      "subtopic": "Appointment delay",
      "review_count": 38,
      "share_of_negative_reviews": 0.42,
      "urgency_high_count": 11,
      "sample_quotes": [
        "Esperé más de una hora a pesar de tener turno",
        "Llegué a tiempo y me atendieron 45 minutos tarde"
      ]
    }
  ],
  "top_positive_topics": [
    {
      "main_topic": "Staff Attitude",
      "subtopic": "Professionalism",
      "review_count": 89,
      "sample_quotes": [
        "El doctor se tomó el tiempo de explicarme todo",
        "Atención excelente, me sentí muy cuidada"
      ]
    }
  ],
  "competitor_summary": {
    "<competitor_name>": {
      "avg_rating": 4.2,
      "top_negative_topic": "Price / Value",
      "top_positive_topic": "Facilities"
    }
  },
  "max_insights": 8
}
```

`competitor_summary` may be `{}` when no competitors are in scope.

---

## Output schema

Return a JSON array of insight objects. Each object MUST match the `insights` table contract:

```json
[
  {
    "insight_rank": 1,
    "insight_type": "recurring_issue | urgent_issue | strength | opportunity | competitor_gap",
    "title": "<≤80 chars, Spanish>",
    "description": "<2-4 sentences, Spanish>",
    "evidence": "<one verbatim quote + one metric, e.g. '\"Esperé más de una hora\" — 38 menciones (42% de las reseñas negativas)'>",
    "recommendation": "<concrete action, Spanish>",
    "expected_business_impact": "reputación | retención | conversión | costos | null",
    "priority": "high | medium | low"
  }
]
```

### Field semantics

- **`insight_rank`**: starts at `1`, consecutive, no gaps. Reflects business priority (most important first).
- **`insight_type`**:
  - `recurring_issue` — appears in many negative reviews.
  - `urgent_issue` — high urgency / safety / immediate impact.
  - `strength` — top positive theme worth doubling down on.
  - `opportunity` — gap or niche the business could exploit.
  - `competitor_gap` — area where competitor is clearly better.
- **`title`**: short headline, Spanish, ≤80 chars.
- **`description`**: 2-4 sentences explaining the finding. Spanish, no jargon.
- **`evidence`**: at least one verbatim quote + at least one metric from the input. Both must come from the input.
- **`recommendation`**: concrete and operational. "Revisar dotación los viernes 19-21h" beats "mejorar la atención".
- **`expected_business_impact`**: qualitative. Avoid quantitative promises ("vas a duplicar las ventas" is forbidden).
- **`priority`**: derived from urgency, frequency and impact. High-frequency + high-urgency = high.

---

## Rules

1. **Use only provided data.** Do not invent metrics, quotes, competitors, or facts.
2. **Quote verbatim.** Copy quotes exactly from `sample_quotes`. No paraphrasing.
3. **Cap at `max_insights`.** Quality over quantity. If the data does not support 8 insights, return fewer.
4. **Balance.** Aim for at least one `strength` and at least one `recurring_issue` if the data supports it. Pure-negative or pure-positive lists are usually wrong.
5. **No fluff.** Skip insights that boil down to "be better at customer service".
6. **Spanish output for client-facing fields.** `title`, `description`, `recommendation` in Spanish. `insight_type`, `priority`, `expected_business_impact` in the controlled English vocabulary.
7. **JSON only.** No commentary, no markdown fences.

---

## Example

### Input

```json
{
  "business_name": "Clínica Smile",
  "business_category": "dental_clinic",
  "period": "all_time",
  "total_reviews": 312,
  "avg_rating": 3.8,
  "sentiment_distribution": {"positive": 0.55, "neutral": 0.18, "negative": 0.27},
  "top_negative_topics": [
    {
      "main_topic": "Waiting Time",
      "subtopic": "Appointment delay",
      "review_count": 38,
      "share_of_negative_reviews": 0.45,
      "urgency_high_count": 11,
      "sample_quotes": [
        "Esperé más de una hora a pesar de tener turno",
        "Llegué a tiempo y me atendieron 45 minutos tarde"
      ]
    }
  ],
  "top_positive_topics": [
    {
      "main_topic": "Staff Attitude",
      "subtopic": "Professionalism",
      "review_count": 89,
      "sample_quotes": [
        "El doctor se tomó el tiempo de explicarme todo",
        "Atención excelente, me sentí muy cuidada"
      ]
    }
  ],
  "competitor_summary": {},
  "max_insights": 5
}
```

### Output

```json
[
  {
    "insight_rank": 1,
    "insight_type": "recurring_issue",
    "title": "Demoras en turnos: el principal motivo de quejas",
    "description": "Los clientes reportan esperas de más de una hora a pesar de haber agendado turno. Es el tema negativo más frecuente del período (45% de las reseñas negativas) y tiene 11 menciones de alta urgencia.",
    "evidence": "\"Esperé más de una hora a pesar de tener turno\" — 38 menciones (45% del total negativo, 11 de alta urgencia)",
    "recommendation": "Auditar la planificación de turnos: revisar buffer entre pacientes, identificar las franjas con mayor desvío y evaluar si la dotación es suficiente en esos horarios.",
    "expected_business_impact": "retención",
    "priority": "high"
  },
  {
    "insight_rank": 2,
    "insight_type": "strength",
    "title": "El equipo médico es el activo más valorado",
    "description": "La atención profesional del staff médico aparece en 89 reseñas positivas, con menciones específicas a la dedicación al paciente. Es la fortaleza más consistente del negocio.",
    "evidence": "\"El doctor se tomó el tiempo de explicarme todo\" — 89 menciones positivas",
    "recommendation": "Capitalizar en comunicación: incluir testimonios sobre la atención profesional en redes y web. Considerar programas de embajadores con los profesionales más mencionados.",
    "expected_business_impact": "conversión",
    "priority": "medium"
  }
]
```

---

## Notes for iteration

- The exact threshold for `priority` should be calibrated with real data — consider derivation rules vs. letting the LLM decide.
- If reports feel "shallow", increase `max_insights` or enrich the input with more context per topic.
- Watch out for the LLM padding insights to hit `max_insights`. If outputs feel formulaic, instruct it to return fewer when data is thin.
