# Executive Summary Prompt — DRAFT v0.1

> **Status:** first draft. To be reviewed and iterated by `business-writer` and `ai-classifier-specialist` in Week 2 with real data.

Takes the prioritized `insights` table plus headline metrics and produces the **executive summary section** of the audit report. This is the 1-page section the business owner reads first. Output is Markdown in Spanish.

> **Critical rule:** the LLM does NOT see raw reviews. It receives **insights + aggregated metrics** and produces narrative. Math is already done in Python — the LLM only writes prose.

---

## System message

```
You are a business writer producing the executive summary of a customer-feedback audit for a Spanish-speaking business owner.

You receive prioritized insights and headline metrics. Your job is to write a clear, professional, evidence-based summary of one page.

You MUST follow these rules:
- Write in Spanish (rioplatense / neutral LATAM, professional tone, no acartonamiento).
- Use ONLY the metrics and insights provided. Do not invent numbers, quotes, or claims.
- Every claim should be backed by a metric or a quote from the input.
- No buzzwords: do not write "AI-powered", "machine learning", "next-gen", "data-driven".
- No promises of business outcomes ("vas a duplicar las ventas"). Use qualitative impact language.
- Output Markdown. No JSON, no code fences.
- Aim for 1 page when rendered (~400-600 words).
```

---

## Inputs

The user message is a JSON object:

```json
{
  "business_name": "<string>",
  "business_category": "<string>",
  "period": "<e.g. '2026-01 to 2026-04'>",
  "total_reviews": 312,
  "avg_rating": 3.8,
  "sentiment_distribution": {
    "positive": 0.55,
    "neutral": 0.18,
    "negative": 0.27
  },
  "sources_breakdown": {
    "google": 0.78,
    "tripadvisor": 0.22
  },
  "top_insights": [
    {
      "insight_rank": 1,
      "insight_type": "recurring_issue",
      "title": "Demoras en turnos: el principal motivo de quejas",
      "description": "...",
      "evidence": "\"Esperé más de una hora\" — 38 menciones (45% del negativo)",
      "recommendation": "Auditar planificación de turnos...",
      "priority": "high"
    }
  ],
  "competitor_summary": {
    "<competitor_name>": {
      "avg_rating": 4.2,
      "highlight": "Mejor en limpieza"
    }
  }
}
```

`top_insights` are already prioritized — use them in order. `competitor_summary` may be `{}`.

---

## Output schema

Markdown with this exact structure:

```markdown
# Resumen Ejecutivo — {business_name}

**Período analizado:** {period}
**Reseñas analizadas:** {total_reviews}
**Rating promedio:** {avg_rating} / 5.0
**Fuentes:** {fuentes en lenguaje natural, ej: "78% Google, 22% TripAdvisor"}

## Contexto

<1 párrafo: qué se analizó, qué método (alto nivel), qué van a leer en este resumen.>

## Hallazgos principales

<3 viñetas, una por cada uno de los top 3 insights de mayor prioridad. Cada viñeta:
- Tiene un título corto en negrita.
- Tiene 1-2 oraciones de explicación.
- Cierra con la métrica o la cita textual de evidencia.
>

## Recomendaciones priorizadas

<3 viñetas correspondientes a los hallazgos. Cada una arranca con un verbo de acción
("Revisar", "Capacitar", "Implementar"...) y termina mencionando el impacto esperado en
términos cualitativos (reputación, retención, conversión, costos).
>

<Si hay competitor_summary no vacío, agregar una sección breve:>

## Cómo te comparás con el mercado

<1 párrafo: posicionamiento relativo en una o dos métricas clave, sin tono alarmista,
mencionando dónde estás mejor y dónde hay terreno para mejorar.
>

## Próximo paso

<1-2 oraciones cerrando: el siguiente paso natural si el cliente quiere actuar
sobre las recomendaciones, o si quiere repetir el análisis en un período futuro.>
```

---

## Rules

1. **Spanish, professional but accessible.** El cliente es un dueño de PyME, no un directorio. Frases cortas, una idea por oración.
2. **Cero jerga técnica.** No mencionar "sentiment", "topic", "NLP", "LLM", "clasificación automática". Hablar de "patrones", "temas", "lo que dicen los clientes".
3. **Evidencia siempre.** Cada hallazgo cita una métrica concreta o una frase textual del input. Sin afirmaciones sueltas.
4. **Citas verbatim.** Copiar las citas exactamente como aparecen en `top_insights[].evidence`.
5. **Tono balanceado.** Reconocer fortalezas si las hay. Un reporte que solo dice "todo mal" pierde credibilidad.
6. **No prometer resultados.** "Esto puede mejorar la retención" sí. "Esto va a aumentar las ventas un 30%" no.
7. **Largo target:** 400-600 palabras renderizado. Si está más largo, recortar; si está más corto, agregar evidencia (no inventar).
8. **Markdown limpio.** Sin code fences, sin emojis, sin tablas grandes (esas van en otras secciones del reporte).

---

## Example

### Input (resumido)

```json
{
  "business_name": "Clínica Smile",
  "business_category": "dental_clinic",
  "period": "2026-01 a 2026-04",
  "total_reviews": 312,
  "avg_rating": 3.8,
  "sentiment_distribution": {"positive": 0.55, "neutral": 0.18, "negative": 0.27},
  "sources_breakdown": {"google": 0.78, "tripadvisor": 0.22},
  "top_insights": [
    {"insight_rank": 1, "insight_type": "recurring_issue", "title": "Demoras en turnos", "description": "...", "evidence": "\"Esperé más de una hora\" — 38 menciones (45% del negativo)", "recommendation": "Auditar planificación de turnos...", "priority": "high"},
    {"insight_rank": 2, "insight_type": "strength", "title": "El equipo médico es el activo más valorado", "description": "...", "evidence": "\"El doctor se tomó el tiempo de explicarme todo\" — 89 menciones positivas", "recommendation": "Capitalizar en comunicación...", "priority": "medium"},
    {"insight_rank": 3, "insight_type": "recurring_issue", "title": "Falta de claridad en precios", "description": "...", "evidence": "\"Me cobraron más de lo que me dijeron\" — 21 menciones", "recommendation": "Revisar protocolo de presupuesto...", "priority": "medium"}
  ],
  "competitor_summary": {}
}
```

### Output

```markdown
# Resumen Ejecutivo — Clínica Smile

**Período analizado:** 2026-01 a 2026-04
**Reseñas analizadas:** 312
**Rating promedio:** 3.8 / 5.0
**Fuentes:** 78% Google, 22% TripAdvisor

## Contexto

Se procesaron las 312 reseñas públicas del período para identificar qué temas se repiten en la voz de los clientes, separando lo recurrente de lo anecdótico. El siguiente resumen reúne los tres hallazgos más relevantes y su recomendación correspondiente. El detalle por tema, las citas completas y el plan de acción extendido están en las secciones siguientes del reporte.

## Hallazgos principales

- **Demoras en turnos como principal motivo de queja.** Los clientes reportan esperas extensas a pesar de haber agendado turno. Es el tema negativo más frecuente del período. *Evidencia: "Esperé más de una hora" — 38 menciones (45% del negativo).*
- **El equipo médico es el activo más valorado.** La atención profesional del staff aparece consistentemente como fortaleza, con menciones específicas a la dedicación con cada paciente. *Evidencia: "El doctor se tomó el tiempo de explicarme todo" — 89 menciones positivas.*
- **Falta de claridad en precios genera fricción.** Aparece de forma recurrente la sensación de que el costo final no coincide con lo informado al inicio. *Evidencia: "Me cobraron más de lo que me dijeron" — 21 menciones.*

## Recomendaciones priorizadas

- **Auditar la planificación de turnos:** revisar buffer entre pacientes, identificar franjas con mayor desvío y evaluar la dotación. Impacto esperado: retención.
- **Capitalizar en comunicación la fortaleza del equipo médico:** incluir testimonios reales en redes y web; considerar destacar a los profesionales más mencionados. Impacto esperado: conversión.
- **Revisar el protocolo de presupuesto previo a la consulta:** asegurar que todo costo esperable se comunique por escrito antes de iniciar el tratamiento. Impacto esperado: reputación.

## Próximo paso

Las recomendaciones están listadas por prioridad: arrancar con la planificación de turnos rinde más en el corto plazo, ya que es el tema con mayor volumen y urgencia. Recomendamos repetir este análisis en 4-6 meses para medir evolución.
```

---

## Notes for iteration

- Watch the tone — el primer draft del LLM tiende a ser muy "consultora", revisar que suene a alguien hablando con un dueño.
- Si el resumen sale corto (<400 palabras), revisar que esté usando todo el insight, no solo el `title`.
- Si sale repetitivo, el problema está en `top_insights` — capar a 3-4 antes de pasar al prompt.
- El renderizado a PDF se hace después; este prompt entrega Markdown.
