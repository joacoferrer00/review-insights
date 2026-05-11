# Architecture

Data flow for `review-insights`. Run with `python run_pipeline.py --client <slug>`.

---

## Pipeline

```
  Config resolution
  ─────────────────
  clients/<slug>/config.yaml          →  business_name, industry, language, places (URLs + roles)
  industries/<industry>/taxonomy.yaml →  topics list (with label_es / label_en per topic)
  industries/<industry>/prompts/      →  classification, enrichment, exec_summary (Jinja2 templates)
  src/review_insights/i18n/<lang>.yaml →  UI strings for PDF and dashboard

  Step 0 — fetch (Apify)
  ──────────────────────
  apify_client.fetch_reviews()
    • Calls Apify crawler-google-places with reviewsSort: "newest"
    • Fetches up to --limit reviews per place
    • Date filter: forward from max(date) in raw.csv (default)
                   or --no-date-filter / --from-date / --to-date
    • Place ID matching: uses item["inputStartUrl"] (the original URL we passed, contains
      hex place ID 0x...:0x...) to map each result to its canonical business_name.
      Fallback: item["title"]. Note: item["url"] uses ChIJ... format — regex won't match it.
    • Output: clients/<slug>/data/0_input/<place>_reviews.json

  Step 1 — ingestion
  ──────────────────
  load_reviews(json_files)
    • Validates schema, attaches business_name from canonical_name
    • Merges into raw.csv via dedup on review_id (keep first)
    • Logs: N new reviews merged (total: M)
    • Output: clients/<slug>/data/1_raw/raw.csv

  Step 2 — cleaning                         SKIPPED if no new reviews
  ──────────────────
  clean_reviews(new_raw)
    • Dedup, date parsing, text normalization, has_text flag
    • Appends only new rows to existing reviews_clean.csv
    • Output: clients/<slug>/data/2_clean/reviews_clean.csv

  Step 3 — classification (LLM)             SKIPPED if no new reviews
  ──────────────────────────────
  classify_reviews(new_clean, provider, prompt, topics, language)
    • Batches of 5 reviews per LLM call
    • Pydantic validation → retry x3 → fallback to single-review call
    • Expands to 1–N rows per review (one per topic mention)
    • Appends only new rows to existing reviews_classified.csv
    • Output: clients/<slug>/data/3_classified/reviews_classified.csv
              (1 row per review_id × mention_id — canonical)

  Step 4 — aggregation                      ALWAYS runs (~50ms, pure pandas)
  ────────────────────
  aggregate(classified_df)
    • Counts, percentages, urgency scores, priority ranking
    • total_reviews / avg_rating always via nunique(review_id)
    • Zero LLM
    • Output: clients/<slug>/data/4_aggregated/aggregated.csv
              clients/<slug>/data/4_aggregated/insights.csv

  Step 5 — enrichment (LLM)                SKIPPED if metrics unchanged
  ──────────────────────────
  enrich_insights(insights_df, classified_df, provider, prompt, language)
    • 1 LLM call per (business × topic)
    • Input: metrics + top 5 quotes from reviews_classified
    • Returns: title, description, evidence, recommendation (Pydantic)
    • Re-enriches only topics whose metrics changed since last run
    • Output: clients/<slug>/data/5_enriched/insights_enriched.csv

  Step 6 — PDF                              SKIPPED if no new data
  ────────────
  render_pdf(business, aggregated_df, enriched_df, provider, prompt, language)
    • Loads strings = load_strings(language) for all UI labels
    • Renders exec_summary prompt as Jinja2 template ({{ language_name }}, {{ style_note }})
    • 1 LLM call for executive summary narrative (~400 words)
    • Jinja2 → HTML (audit_report.html, all strings via t=strings) → Playwright → PDF
    • Output: clients/<slug>/outputs/reports/<Business>_audit.pdf

  Dashboard (Streamlit Cloud, always live)
  ─────────────────────────────────────────
  app.py?client=<slug>
    • Reads: aggregated.csv, insights_enriched.csv, reviews_classified.csv
    • Loads strings = load_strings(cfg.language) — all labels, tab names, chart axes
    • Sentiment/urgency stored as canonical keys (positive/negative, high/medium/low);
      mapped to display labels via strings["label_*"] at render time
    • No LLM, no pipeline — pure read + Plotly charts
    • Deployed at https://review-insights-audit.streamlit.app
```

---

## Incremental behavior

Each step only processes rows not already in its output file.

| Step | Trigger to rerun | How |
|---|---|---|
| 0 — fetch | Always (unless `--skip-fetch`) | Overwrites JSONs in `0_input/` |
| 1 — ingestion | New JSONs in `0_input/` | Merge by `review_id`, dedup |
| 2 — cleaning | New rows in `raw.csv` not in `reviews_clean.csv` | Appends |
| 3 — classification | New rows in `reviews_clean.csv` not in `reviews_classified.csv` | Appends |
| 4 — aggregation | Always (~50ms) | Full recompute from classified |
| 5 — enrichment | Topics whose metrics changed | Re-enriches changed topics only |
| 6 — PDF | `had_new_data = True` (set when step 3 runs) | Full regeneration |

To rerun from scratch: delete all CSVs under `clients/<slug>/data/`.

---

## LLM calls

| Step | Caller | Batching | Cost model |
|---|---|---|---|
| 3 | `classification/__init__.py` | 5 reviews/call, fallback to 1 | O(n_reviews / 5) |
| 5 | `reporting/insight_enricher.py` | 1 call per (business × topic) | O(businesses × topics) — constant vs review volume |
| 6 | `reporting/report_generator.py` | 1 call per business | O(businesses) |

---

## Module responsibilities

| Module | Owns |
|---|---|
| `i18n/` | `load_strings(language)` → dict of UI strings; `es.yaml` + `en.yaml` |
| `ingestion/apify_client` | Apify API calls, place ID matching via `inputStartUrl`, JSON persistence |
| `ingestion` | JSON → DataFrame, schema validation, merge into raw.csv |
| `cleaning` | Dedup, date parsing, text normalization |
| `llm/` | Provider abstraction — swap via `LLM_PROVIDER` + `LLM_MODEL` env vars |
| `classification` | Batch LLM calls, Pydantic validation, retry logic, multi-mention expansion |
| `aggregation` | All math — counts, ratios, urgency scores, rankings. Zero LLM. |
| `reporting/insight_enricher` | Per-topic LLM enrichment, incremental re-enrichment |
| `reporting/report_generator` | Exec summary LLM call, Jinja2 → Playwright → PDF |
| `reporting/dashboard` | Streamlit charts and data loaders. No LLM. |
| `config.py` | Resolves all paths from `--client` slug. Single source of truth for paths. |

---

## Rules

- **Pydantic on every LLM output.** Raw JSON never used without validation.
- **Math belongs to Python.** LLM receives pre-computed metrics — never counts or calculates.
- **Fail loud.** LLM failures after retries log ERROR and produce null fields — pipeline does not crash.
- **Multi-mention:** `reviews_classified.csv` has 1 row per `(review_id, mention_id)`. Always `nunique(review_id)` for counts.
- **Canonical sentiment/urgency keys:** stored as `positive/neutral/negative` and `high/medium/low` in all CSVs. Translated to display labels at render time via `strings["label_*"]`. Never store translated strings in CSVs.
- **Prompts are Jinja2 templates:** `enrichment.md` and `exec_summary.md` use `{{ language_name }}` and `{{ style_note }}`. Rendered before the LLM call — don't use raw string concatenation.

---

## i18n

Language is set per client in `config.yaml` (`language: es | en`). It flows through the entire pipeline:

```
config.language
  → classify_reviews(language=)     # prompt template rendered with {{ language_name }}
  → enrich_insights(language=)      # prompt template rendered with {{ language_name }}, {{ style_note }}
  → render_pdf(language=)           # strings loaded, prompt rendered, HTML template uses t=strings
  → app.py                          # strings loaded, all labels/tabs/filters from strings dict
```

Adding a new language: add `<lang>.yaml` in `src/review_insights/i18n/`, add the lang code to `LANG_NAMES` in `i18n/__init__.py`, set `language: <lang>` in the client config.