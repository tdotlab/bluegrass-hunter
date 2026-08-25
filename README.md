# Kentucky Web Scout

A small, open-source research agent for finding local businesses that may have no owned website or a weak web presence.

The project is intentionally narrow right now: its region-expansion database covers Kentucky. The single-location research endpoint can still accept any location string, but the settlement-by-settlement region workflow is Kentucky-specific until another state index is added.

## What it does

1. Takes a business category and either one location or a Kentucky region.
2. Uses Tavily for live web search.
3. Gives the evidence to DeepSeek for structured synthesis.
4. Scores candidates deterministically for evidence quality, legitimacy, service value, local fit, and website weakness.
5. Produces a JSON or Markdown report for human review.

It stops at research. It does not contact businesses, send email, or make claims that a business is inactive based on one missing search result.

## How the Kentucky region workflow works

The checked-in settlement index combines:

- USGS Geographic Names Information System (GNIS) populated places.
- The 2025 U.S. Census Gazetteer place file.
- A deterministic deduplication and classification pass.
- A point-in-polygon filter for named anchor towns.

Historical places remain in the source data for provenance but are excluded from the searchable queue. The index can be regenerated with:

```bash
python scripts/build_place_index.py
```

The region endpoint can either expand a triangle or other polygon from three to five anchors, or accept an explicit list of settlement names:

```json
{
  "category": "independent service businesses",
  "settlement_names": ["Paris", "Cynthiana", "Flemingsburg", "Mount Sterling"],
  "town_limit": 4,
  "count": 10,
  "verify": true
}
```

Send that JSON to `POST /research-region`. Use `"output_format": "markdown"` for a downloadable Markdown report.

## API

Readiness:

```bash
curl https://your-service.onrender.com/health
```

Single-location research:

```json
{
  "category": "independent plumbers",
  "location": "Cynthiana, Kentucky",
  "count": 10,
  "output_format": "json"
}
```

Region expansion:

```json
{
  "anchors": ["Lexington", "Maysville", "Morehead"]
}
```

If `RESEARCH_TOKEN` is set, send it as a Bearer token. Keep the token and API keys in environment variables; never commit them.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Required integrations:

- `DEEPSEEK_API_KEY` — reasoning/synthesis.
- `TAVILY_API_KEY` — live web search.

Optional settings include `RESEARCH_TOKEN` and `LEAD_AGENT_MODEL`. See `.env.example`.

## Render

`render.yaml` defines the Python web service, builds the settlement index during deployment, starts FastAPI with Uvicorn, and links the deployment to the existing `DeepSeek` environment group. The public source repository contains the deployment shape, not any secret values.

## Repository layout

- `agent.py` — search/reasoning workflow.
- `geography.py` — Kentucky index loading, anchor resolution, and polygon selection.
- `scripts/build_place_index.py` — reproducible public-data builder.
- `data/kentucky_settlements.json` — generated settlement index.
- `scoring.py` — deterministic ranking.
- `report.py` — JSON/Markdown report rendering.
- `reports/examples/` — synthetic example output.
- `docs/research-rubric.md` — scoring notes.

## Status

This is a working prototype, not a finished commercial product. The public release is meant to show the architecture and make the research workflow reproducible. Real operational reports and contact details stay outside the public release.
