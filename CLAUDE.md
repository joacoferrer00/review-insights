# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Constitución del proyecto — leé este archivo completo antes de hacer nada en este repo.**

---

## Qué es esto

**review-insights** — servicio productizado que toma reseñas públicas de clientes y las convierte en un reporte ejecutivo + dashboard accionable. No es un SaaS, no es una plataforma. El entregable al cliente es un **PDF ejecutivo (5-8 páginas) + Streamlit dashboard navegable + 30 min de presentación**.

Nombre comercial: **Review Intelligence Audit**.

**Principio:** Business value first. Toda decisión técnica se justifica contra: mejor insight, mejor demo, mejor venta, mejor reproducibilidad, o mejor confiabilidad. Si no aporta a ninguna, no entra.

---

## Estado actual

| Fase | Estado | Qué está hecho |
|---|---|---|
| 1 — Fundación | ✅ | Repo, dataset (250 reviews, 4 restaurantes Av. Gauss, Córdoba), Gemini 2.5 Flash operativo |
| 2 — Pipeline | ✅ | Pipeline completo (ingestion → cleaning → classification → aggregation), 3 tablas canónicas, multi-mention schema |
| 3 — Producto vendible | ✅ | Streamlit dashboard + PDF ejecutivo con LLM, activos de venta (case study, LinkedIn draft) |
| 4 — Infraestructura productiva | ✅ | Multi-cliente + multi-industria: `--client <slug>`, `clients/*/config.yaml`, `industries/*/taxonomy.yaml`, pipeline incremental, Apify con canonical names, Streamlit Cloud live |
| 5 — i18n + supermarkets | ✅ | Campo `language: es\|en` en config controla PDF, dashboard y outputs de LLM. Industria `supermarkets` con cliente Wegmans (2 sucursales). Fix de place ID lookup en Apify. |

**Clientes activos:**
- **IDA** (`language: es`): 800 reviews, 4 restaurantes — IDA Restaurant Bar, Vittorio Ristorante, El Mesón de Gauss, Mitica (Cerro de las Rosas, Córdoba).
- **Wegmans** (`language: en`): 400 reviews, 2 sucursales — Hanover NJ (target) + Chesapeake VA (benchmark).

**Dashboard live:** `https://review-insights-audit.streamlit.app?client=ida` | `?client=wegmans`

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| Runtime | Python, `.venv` del proyecto — SIEMPRE usar `.venv\Scripts\python`, nunca el Python global |
| LLM | Gemini 2.5 Flash Lite (clasificación y enrichment). Upgrade a `gemini-2.5-flash` cambiando `LLM_MODEL` en `.env` |
| Validación | Pydantic — outputs de LLM siempre validados, sin excepción |
| Dashboard | Streamlit + Plotly |
| PDF | Jinja2 + Playwright |
| Data | pandas, CSV — sin base de datos |
| Scraping | Apify (extracción inicial de Google Maps reviews) |

---

## Estructura del repo

```
clients/
  <slug>/
    config.yaml          # business_name, industry, language, places (URLs + roles), branding
    data/                # gitignoreado salvo 3_classified/ → 5_enriched/
    outputs/             # PDFs, exports — gitignoreado

industries/
  <industry>/
    taxonomy.yaml        # topics + descripciones + label_es + label_en
    prompts/             # classification, enrichment, exec_summary — Jinja2 templates

src/review_insights/
  i18n/                 # load_strings(language) → dict; es.yaml + en.yaml
  ingestion/            # JSON → raw.csv
  cleaning/             # dedup, normalización → reviews_clean.csv
  llm/                  # base.py (interfaz) + gemini_provider.py
  classification/       # batch LLM (5/llamada) + Pydantic + retries → reviews_classified.csv
  aggregation/          # pure pandas, cero LLM → aggregated.csv + insights.csv
  reporting/
    insight_enricher.py # LLM enriquece insights → insights_enriched.csv
    report_generator.py # PDF ejecutivo
    dashboard.py        # app Streamlit

run_pipeline.py          # pipeline end-to-end
app.py                   # entry point Streamlit (?client=<slug>)
```

---

## Comandos de desarrollo

```bash
# Dashboard local
.venv\Scripts\streamlit run app.py -- --client ida   # http://localhost:8501?client=ida

# Linting (ruff, line-length 100)
.venv\Scripts\ruff check src/
.venv\Scripts\ruff check src/ --fix

# Tests (directorio tests/ aún no implementado)
.venv\Scripts\pytest
```

---

## CLI

```bash
python run_pipeline.py --client ida                          # forward: solo reviews nuevas
python run_pipeline.py --client ida --no-date-filter         # sin filtro de fecha, trae todo
python run_pipeline.py --client ida --limit 200              # máx 200 reviews por place
python run_pipeline.py --client ida --from-date 2025-01-01   # desde esta fecha
python run_pipeline.py --client ida --to-date 2025-06-01     # hasta esta fecha
python run_pipeline.py --client ida --skip-fetch             # usa JSONs existentes, sin Apify
```

**Nota:** `--backfill` fue removido — Apify no respeta `reviewsEndDate` de forma confiable. Para histórico completo, usar `--no-date-filter --limit 500` en la primera corrida.

---

## Las tablas canónicas (única fuente de verdad)

Paths relativos a `clients/<slug>/data/`:

| Archivo | Descripción | Granularidad |
|---|---|---|
| `2_clean/reviews_clean.csv` | Reviews limpias | 1 fila por review |
| `3_classified/reviews_classified.csv` | Reviews clasificadas | 1 fila por `(review_id, mention_id)` — multi-mention |
| `4_aggregated/aggregated.csv` | Métricas por negocio y tema | 1 fila por `(business, topic)` |
| `4_aggregated/insights.csv` | Insights rankeados | generados por Python |
| `5_enriched/insights_enriched.csv` | Insights con título, evidencia y recomendación | generados por LLM |

Cualquier columna nueva se discute en conversación antes de existir en código. Ver `architecture.md` para el diseño del sistema.

**Qué se commitea:**
- ✅ `clients/*/config.yaml`
- ✅ `clients/*/data/3_classified/` → `5_enriched/` — CSVs que Streamlit Cloud necesita
- ❌ `clients/*/data/0_input/` — JSONs crudos de Apify
- ❌ `clients/*/data/1_raw/` y `2_clean/` — intermedios, se regeneran
- ❌ `clients/*/outputs/` — PDFs y artefactos generados

---

## Principios de engineering

- **Pydantic siempre**: output de LLM → Pydantic. Si falla, se rechaza o reintenta. Nunca se procesa JSON crudo sin validar.
- **Las matemáticas son de Python**: conteos, porcentajes, rankings — Python. El LLM solo clasifica e interpreta.
- **Provider abstraction**: `llm/base.py` define la interfaz. Swap de provider = cambiar env var, no tocar código.
- **Sin abstracciones prematuras**: tres líneas similares es mejor que un helper que nadie va a reusar.
- **Comentarios solo cuando el "por qué" no es obvio**. Nunca comentarios que repiten el "qué".
- **Multi-mention**: `reviews_classified.csv` tiene 1 fila por `(review_id, mention_id)`. `total_reviews` y `avg_rating` siempre con `nunique(review_id)`.
- **i18n por config**: el campo `language: es|en` en `config.yaml` controla todo — strings del PDF/dashboard vía `load_strings()`, idioma de outputs LLM vía `{{ language_name }}` en los prompts. Los prompts son Jinja2 templates: si editás un `.md` de prompt, verificar que los `{{ }}` sigan intactos.

---

## Working style

Cuando te pida un cambio:
1. **Antes de tocar código**: decime qué archivos vas a tocar y qué propones.
2. Si es razonable, apruebo.
3. Recién ahí implementás.
4. Después del cambio: qué cambió, cómo se prueba, qué supuestos asumiste.

---

## Convenciones de lenguaje

- **Inglés**: código fuente, `README.md`, `docs/technical/*`, `prompts/*.md`.
- **Español**: este archivo, `.claude/agents/*.md`, `PROJECT_BRIEF.md`, `ROADMAP.md`, `DECISIONS.md`, `docs/product/*`, reportes al cliente, pitch, outreach.

---

## Seguridad

- `.env` **NUNCA** se commitea. Solo `.env.example`.
- API keys, credenciales, datos de clientes: jamás en el repo.

## Commits

- **NUNCA** agregar `Co-Authored-By: Claude` ni ninguna firma de IA. Los commits son de Joaquín.
- Mensajes en inglés, formato `type: description` — `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.
