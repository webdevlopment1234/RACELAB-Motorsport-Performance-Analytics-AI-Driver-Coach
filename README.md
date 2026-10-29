# F1 Analytics — RACELAB

Motorsport performance analytics and an AI driver coach built on Formula 1
data: historical race analytics, post-qualifying race prediction, pace and
strategy coaching, live timing, and an LLM-powered race assistant.

## Architecture

Three layers with clean separation:

```
┌────────────────────┐      ┌─────────────────────┐      ┌──────────────────────┐
│  frontend/ (Next.js)│ HTTP │  backend/ (Flask)   │ calls │  src/f1_analytics/   │
│  pages + charts +   │─────▶│  app factory,       │─────▶│  analytics, live,    │
│  live polling       │ JSON │  blueprints, services│      │  models, coach, DB   │
└────────────────────┘      └─────────────────────┘      └──────────────────────┘
```

- **Front end — Next.js 15 (App Router, TypeScript)**: all 10 dashboard pages
  (Race Intelligence, Analytics, Drivers, Constructors, Circuits, LIVE,
  Predictions, Coach, Assistant, Data Health), dark RACELAB skin, Recharts
  visualisation, 5-second live polling. Talks only REST.
- **Back end — Flask 3**: app factory + Blueprint API router + service layer
  (live-session registry, background training jobs, report adapters) +
  JSON-safe DataFrame serialisation. CORS-restricted to the front-end origin.
- **Core — `f1_analytics` Python package**: untouched domain logic — analytics,
  SQLite queries, live providers (OpenF1 / Mock / Replay), models, coach and
  the LLM assistant. Works fully offline against the bundled dataset.

The old Streamlit dashboard (`dashboard/`) is kept as a legacy fallback and no
longer part of the primary front end.

---

## Features

| Area | What it does |
| --- | --- |
| **Race Intelligence** | Flagship screen: live/track session view with leaderboard, weather, race control, intervals, stints/tyre strategy and the AI coach driven by live polling. |
| **Analytics** | Driver, constructor and circuit summaries plus full race calendar (1950-2024+) from the bundled SQLite database. |
| **Predictions** | Post-qualifying models (`finish`, `is_dnf`, `is_podium`, `is_winner`) with status, background training and scoring form generated from each artifact's input contract. |
| **Coach** | Evidence-based coaching: race pace gap, sector consistency, best-lap tyre context — with explicit caveats when data is insufficient. |
| **LIVE** | Providers: `openf1` (free API, no key), `mock` (offline), `replay` (saved snapshots from `dataset/live_replays/`). Preview before starting, save snapshots for weekday analysis. |
| **Assistant** | Tool-using LLM assistant; rule-based fallback when no API key is set. |
| **Data Health** | Data asset status + validation/drift suite (CSV vs SQLite vs parquet vs tracks.yaml). |

## Requirements

- **Back end**: Python 3.10 – 3.12, Node 18+ only needed for the front end.
- Optional: internet connection for live OpenF1 timing and LLM features.
- Everything in the core package runs fully offline against the bundled database.

## Back end setup (Flask API)

Create/activate a virtual environment, then install core + server extra:

```powershell
pip install -e .[server]      # adds flask + flask-cors
```

with full extras (live timing / assistant / dev tests):

```powershell
pip install -e .[live,assistant,server,dev]
```

Run the API (serves http://127.0.0.1:5000):

```powershell
python backend/run.py
```

Key endpoints (all JSON):

```text
GET  /api/health                     GET  /api/data-source
GET  /api/data/status                GET  /api/data/validations
GET  /api/calendar                   GET  /api/races/<id>/results
GET  /api/standings?year=2023        GET  /api/drivers | /api/drivers/<id>
GET  /api/drivers/head-to-head?a=&b= GET  /api/constructors[...] (+pit-stops, points)
GET  /api/circuits | /winners | /pace
GET  /api/models/status              POST /api/models/train     (background job)
GET  /api/models/train/status        POST /api/predict          {task, row}
GET  /api/coach/laps|race            POST /api/assistant/ask    {question}
GET  /api/live/providers|replays     POST /api/live/session     {provider}
GET  /api/live/snapshot              POST /api/live/refresh
POST /api/live/save-snapshot         GET  /api/live/coach       GET /api/live/preview?provider=mock
```

Loads: CORS origins/hosts/ports are env-configurable (`F1_CORS_ORIGINS`,
`F1_API_HOST`, `F1_API_PORT`).

## Front end setup (Next.js)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Point the app at a non-default API with
`NEXT_PUBLIC_API_URL`; the default is `http://localhost:5000`.

## Configuration

Defaults live in `src/f1_analytics/config.py`. A repo-root `.env` file is
loaded automatically; already-set environment variables always win.

### Assistant & paths

| Variable | Default | Purpose |
| --- | --- | --- |
| `F1_ASSISTANT_API_KEY` | *(empty)* | OpenAI-compatible API key |
| `F1_ASSISTANT_BASE_URL` | *(empty)* | Optional custom API base URL |
| `F1_ASSISTANT_MODEL` | `gpt-4o-mini` | Model name for the assistant |
| `F1_ROOT_DIR` | repo root | Fallback base for data/models |
| `F1_DATA_DIR` | `dataset/` | Dataset directory |
| `F1_MODELS_DIR` | `models/` | Trained model artifacts |

Without an API key the assistant uses its rule-based fallback, so nothing
breaks.

### CLI (offline, no front end needed)

Installing the package still exposes the `f1-analytics` command:

```powershell
f1-analytics data-status      # show which data files are present/missing
f1-analytics validate-data    # run the validation / drift suite
f1-analytics models-status    # dry-run check for model artifacts
f1-analytics train            # train finish/dnf/podium/winner artifacts
f1-analytics doctor           # data-status + models-status + source summary
```

Model tasks train on chronological splits (train ≤ 2022, val 2023-2024,
test 2025, holdout 2026+); artifacts are written to `models/` and gitignored.

## Tests

```powershell
python tests/run_tests.py                # offline, pytest-free runner
python -m pytest tests -q                # via pytest
.venv/Scripts/python.exe -m pytest tests/test_api.py -q   # Flask API only
```

39 tests: Streamlit-free offline core tests plus 9 Flask API smoke tests
that use the app factory's test client (no dataset required; data-dependent
checks degrade gracefully).

## Repository layout

```
src/f1_analytics/   # core package (domain logic)
  analytics/        # driver / constructor / circuit summaries
  assistant/        # LLM race assistant + rule-based fallback
  coach/            # pace & strategy coaching reports
  database/         # SQLite queries against the bundled dataset
  features/         # feature contract definitions
  live/             # live timing providers (OpenF1, Mock, Replay)
  models/           # race prediction artifacts (finish/dnf/podium/winner)
  preprocessing/    # data validation & schemas
  simulation/       # race simulation
backend/            # Flask API server
  app/              # create_app factory, blueprints/, services/, config, errors
  run.py            # dev entrypoint (python backend/run.py)
frontend/           # Next.js 15 App Router app
  app/              # the 10 pages (client components + polling)
  components/       # NavBar, DataTable, panels/pills/findings
  lib/              # typed API client (api.ts) + polling hooks (useApi.ts)
dataset/            # local dataset + saved live replay snapshots
models/             # trained model artifacts (gitignored outputs)
tests/              # core + Flask API smoke tests
dashboard/          # legacy Streamlit front end (kept as fallback)
```
