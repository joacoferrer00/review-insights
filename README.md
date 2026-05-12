# review-insights

A productized service that turns raw Google Maps reviews into an executive report + interactive dashboard.

**Live demo:** https://review-insights-audit.streamlit.app?client=wegmans

![Dashboard](docs/assets/dashboard_overview.png)

## What you get

- **Interactive dashboard** — sentiment breakdown, topic analysis, urgency heatmap, competitor benchmark, action plan.
- **Executive PDF report** — 5-8 pages, ready to present. No technical background needed to read it.
- **Prioritized action plan** — ranked by mention volume × urgency × % negative sentiment.

## How it works

Raw Google Maps reviews → LLM classification (sentiment, topic, urgency) → aggregation → dashboard + PDF.

```
ingestion → cleaning → classification → aggregation → dashboard / report
```

## Stack

- Python, pandas, Pydantic
- Gemini 2.5 Flash (classification + insight enrichment)
- Streamlit + Plotly (dashboard)
- Jinja2 + Playwright (PDF)

## Features

- **Multi-client** — each client lives in `clients/<slug>/config.yaml`, no code changes needed to onboard a new one.
- **Multi-industry** — topic taxonomies and LLM prompts are defined per industry (`restaurants`, `supermarkets`, …).
- **Multi-language** — `language: es | en` in the client config controls LLM outputs, PDF labels, and dashboard strings end-to-end.
- **Incremental pipeline** — only new reviews are classified; only changed topics are re-enriched.

## Quick start

```bash
git clone https://github.com/joacoferrer00/review-insights.git
cd review-insights

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -e .

cp .env.example .env
# Fill in LLM_API_KEY (Gemini) and optionally APIFY_API_KEY

# Run the pipeline using existing data (no Apify call needed)
python run_pipeline.py --client ida --skip-fetch

# Launch the dashboard
streamlit run app.py
```

## Running the pipeline

```bash
# Use existing JSON exports (no Apify call) — most common during development
python run_pipeline.py --client ida --skip-fetch

# Fetch new reviews from Apify, then run pipeline (requires APIFY_API_KEY in .env)
python run_pipeline.py --client ida

# Fetch reviews within a specific date range
python run_pipeline.py --client ida --from-date 2025-01-01 --to-date 2025-06-01

# Cap reviews per place — useful for quick tests
python run_pipeline.py --client ida --limit 20 --skip-fetch
```

The pipeline is incrementally idempotent:

| Step | Behavior |
|---|---|
| 0 — fetch | Calls Apify. Skipped with `--skip-fetch`. |
| 1 — ingestion | Merges new JSONs into raw.csv by `review_id`. Re-running with the same data adds 0 rows. |
| 2 — cleaning | Detects new `review_id`s not yet in reviews_clean.csv, cleans only those, appends. Skipped if no new reviews. |
| 3 — classification | Skips already-classified `review_id`s. Skipped if no new reviews. |
| 4 — aggregation | Always recomputes (~50ms, pure pandas, no LLM). |
| 5 — enrichment | Re-enriches only topics whose metrics changed. Skipped if nothing changed. |
| 6 — PDF | Regenerates only when new reviews were classified. |

## Adding a new client

1. Create `clients/<slug>/config.yaml` — see `clients/ida/config.yaml` as reference.
2. Run `python run_pipeline.py --client <slug>` to fetch reviews from Apify and run the full pipeline.

   If you have existing Apify JSON exports, drop them into `clients/<slug>/data/0_input/` and use `--skip-fetch`:
   ```bash
   python run_pipeline.py --client <slug> --skip-fetch
   ```

No code changes required.

## Repo layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit dashboard entry point |
| `run_pipeline.py` | End-to-end pipeline runner |
| `src/review_insights/` | Package: ingestion, cleaning, classification, aggregation, reporting |
| `src/review_insights/i18n/` | Language strings loaded at runtime (`es.yaml`, `en.yaml`) |
| `clients/<slug>/config.yaml` | Per-client config: places, roles, language, branding |
| `clients/<slug>/data/` | Pipeline outputs for that client (gitignored except processed CSVs) |
| `industries/<industry>/taxonomy.yaml` | Topic taxonomy loaded at runtime |
| `industries/<industry>/prompts/` | LLM prompts parametrized by industry (Jinja2 templates) |

## License

Proprietary — all rights reserved.

## Author

[Joaquin Ferrer](https://www.linkedin.com/in/joaquínferrer) — Industrial & Analytics Engineer.
