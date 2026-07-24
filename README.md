# Lumenci Assistant

A patent infringement claim chart tool: upload a claim chart and evidence
documents, get an AI first-pass Strong/Moderate/Weak classification per row,
then refine it conversationally with a human-in-the-loop accept/reject/modify
gate on every change. See `docs/prd.md` for the full product spec.

## Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) running locally with the `qwen2.5:3b` model
  pulled (`ollama pull qwen2.5:3b`) — the backend talks to it by default. A
  hosted OpenRouter model can be used instead; see Configuration below.

## Running the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The SQLite DB (`app.db`) and schema are created automatically on first
startup. The API is served at `http://localhost:8000`.

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

The app is served at `http://localhost:5173` (Vite's default) and expects
the backend at `http://localhost:8000` (override with a `VITE_API_BASE_URL`
env var if needed).

## Configuration

The backend reads these environment variables (all optional, sensible
defaults shown):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` (local) or `openrouter` (hosted) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Local model name |
| `OPENROUTER_API_KEY` | — | Required only if `LLM_PROVIDER=openrouter` |
| `OPENROUTER_MODEL` | `qwen/qwen-2.5-72b-instruct` | Hosted model route |
| `SQLITE_PATH` | `app.db` | DB file location |

## Trying it out

Sample data is included at the repo root for testing the full flow without
needing your own files:

- `sample_chart.csv`, `sample_chart_router.csv`, `sample_chart_thermostat.csv`
  — sample claim charts, usable with "Upload Claim Chart".
- `sample_evidence.txt`, `sample_evidence_router_manual.txt`,
  `sample_evidence_router_spec.txt`, `sample_evidence_thermostat_faq.txt`,
  `sample_evidence_thermostat_spec.txt` — matching evidence documents,
  usable with "Upload Evidence".

Pair a chart with its matching evidence file(s) (e.g. the router chart with
the router manual/spec) to exercise the full upload → generate → chat flow.

## Running backend tests

```bash
cd backend
pytest
```
