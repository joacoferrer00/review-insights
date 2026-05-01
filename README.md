# review-insights

A productized service that turns raw customer reviews into an executive report + interactive dashboard.

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

## Quick start

```bash
git clone <repo-url>
cd review-insights
pip install -e .

cp .env.example .env
# Fill in LLM_API_KEY

# Run the pipeline using existing data (no Apify call)
python run_pipeline.py --client ida --skip-fetch

# Launch the dashboard
streamlit run app.py
```

## Running the pipeline

```bash
# Use existing JSON exports (no Apify call) — most common during development
python run_pipeline.py --client ida --skip-fetch

# Fetch new reviews from Apify, then run pipeline (requires Apify token in .env)
python run_pipeline.py --client ida

# Fetch only older reviews not yet in the dataset (backfill)
python run_pipeline.py --client ida --backfill

# Fetch reviews within a specific date range
python run_pipeline.py --client ida --from-date 2025-01-01 --to-date 2025-06-01

# Cap reviews per place — useful for quick tests (Apify fetch only)
python run_pipeline.py --client ida --limit 20 --skip-fetch
```

Each pipeline step is idempotent — if the output file already exists, the step is skipped. Delete the relevant file to force a re-run from that step.

## Adding a new client

1. Create `clients/<slug>/config.yaml` — see `clients/ida/config.yaml` as reference.
2. Drop Apify JSON exports into `clients/<slug>/data/0_input/`.
3. Run `python run_pipeline.py --client <slug> --skip-fetch`.

No code changes required.

## Repo layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit dashboard entry point |
| `run_pipeline.py` | End-to-end pipeline runner |
| `src/review_insights/` | Package: ingestion, cleaning, classification, aggregation, reporting |
| `clients/<slug>/config.yaml` | Per-client config: places, roles, branding |
| `clients/<slug>/data/` | Pipeline outputs for that client (gitignored except processed CSVs) |
| `industries/<industry>/taxonomy.yaml` | Topic taxonomy loaded at runtime |
| `industries/<industry>/prompts/` | LLM prompts parametrized by industry |

## License

Proprietary — all rights reserved.

## Author

[Joaquin Ferrer](https://www.linkedin.com/in/joaquínferrer) — Industrial & Analytics Engineer.
