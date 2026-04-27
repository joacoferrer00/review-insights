# review-insights

A productized service that turns raw customer reviews into actionable business insights.

Given a set of customer reviews (Google reviews, surveys, support tickets, etc.), the pipeline classifies each one by sentiment, topic, urgency and actionability, aggregates the results into business metrics, and produces an executive-ready report with prioritized recommendations.

## What this is

- A **service**, not a SaaS. The deliverable is a report + dashboard, not a self-serve platform.
- **End-to-end pipeline**: ingestion → cleaning → LLM classification → aggregation → dashboard → executive report.
- **LLM-agnostic**: provider abstraction so we can swap between Gemini, OpenAI, or local models.

## Status

Week 1 of a 4-week sprint. Skeleton + dataset stage. See [`ROADMAP.md`](./ROADMAP.md).

## Stack

- Python 3.11+
- pandas, pydantic, python-dotenv
- Gemini Flash (default) or OpenAI mini for classification
- Power BI for dashboards
- Markdown / PDF for reports

## Quick start

```bash
# Clone and install
git clone <repo-url>
cd review-insights
pip install -e .

# Configure
cp .env.example .env
# Then fill in LLM_API_KEY in .env

# Run (modules will be added across weeks 1-4)
```

## Repo layout

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Project constitution. Read this first if you are Claude or new to the project. |
| `PROJECT_BRIEF.md` | Mission, target customer, offer. |
| `ROADMAP.md` | 4-week plan with weekly deliverables. |
| `DECISIONS.md` | Append-only log of technical and product decisions. |
| `.claude/agents/` | 8 specialized Claude Code subagents (PM, architect, data eng, etc.). |
| `docs/technical/` | Architecture, data contracts, classification schema, evaluation. |
| `docs/product/` | ICP, offer, pricing, outreach scripts (Spanish). |
| `docs/reports/` | Executive report templates (Spanish). |
| `prompts/` | Versioned LLM prompts (classification, summary, insights). |
| `src/review_insights/` | Python package: ingestion, cleaning, classification, aggregation, reporting, llm. |
| `data/` | `raw/` and `processed/` are gitignored. `sample/` is versioned. |
| `outputs/` | Dashboards, reports, exports (gitignored). |

## License

Proprietary — all rights reserved. Reach out before reusing.

## Author

[Joaquin Ferrer](https://www.linkedin.com/in/joaquínferrer) — Industrial & Analytics Engineer.
