# F1 Analytics — RACELAB

Motorsport performance analytics and an AI driver coach built on Formula 1
data: historical race analytics, post-qualifying race prediction, pace and
strategy coaching, live timing, and an LLM-powered race assistant.

The core package works **fully offline** against a bundled SQLite dataset.
Live timing and the LLM assistant are optional extras that light up with a
network connection.

---

## Features

| Area | What it does |
| --- | --- |
| **Race Intelligence** | Flagship dashboard screen: live/historical race view with P1-P4 timing, a track map, telemetry gauges, a speed/throttle/brake/gear/delta trace, tyre strategy, and the AI coach. Works offline. |
| **Analytics** | Driver, constructor and circuit summaries queried from the local database. |
| **Predictions** | Post-qualifying model artifacts (`finish`, `is_dnf`, `is_podium`, `is_winner`) trained on chronologically split data. |
| **Coach** | Lap-by-lap pace and strategy coaching reports (tyre degradation, pit windows, pace deltas). |
| **LIVE** | Live timing through pluggable providers: `openf1` (free, no API key), `mock` (offline demo), and `replay` (saved snapshots from `dataset/live_replays/`). |
| **Assistant** | LLM race assistant with tool use; gracefully falls back to a built-in rule-based analyser when no API key is configured. |
| **Data Health** | Validation and drift suite over the bundled dataset. |

---

## Requirements

- Python 3.10 – 3.12
- Optional: internet access for live timing (OpenF1) and LLM features.

Everything else runs fully offline against the bundled local database.

## Installation

Create and activate a virtual environment, then install the profile you
need. All pins, including versioned extras, live in `pyproject.toml`
(PEP 621) — that file is the source of truth.

### Core (everything that works offline)

```powershell
pip install -e .
```

or equivalently:

```powershell
pip install -r requirements.txt
```

### Live timing extras

```powershell
pip install -e .[live]
```

Adds `fastf1>=3.8` for telemetry-aware live timing. Note: the default live
provider (`openf1`) and the offline `mock`/`replay` providers do **not**
require `fastf1`.

### LLM assistant extra

```powershell
pip install -e .[assistant]
```

Adds `openai>=1.30`. Without an API key the assistant automatically uses
its rule-based fallback, so nothing breaks if this extra is skipped.

### Development / tests

```powershell
pip install -e .[dev]          # core + pytest
pip install -e .[live,assistant,dev]   # all extras
```

## Configuration

Defaults live in `src/f1_analytics/config.py`. A repo-root `.env` file is
loaded automatically (via `python-dotenv`); already-set environment
variables always win.

### Assistant settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `F1_ASSISTANT_API_KEY` | *(empty)* | OpenAI-compatible API key |
| `F1_ASSISTANT_BASE_URL` | *(empty)* | Optional custom API base URL |
| `F1_ASSISTANT_MODEL` | `gpt-4o-mini` | Model name for the assistant |

Without an API key the assistant uses its rule-based fallback.

### Path overrides

| Variable | Default | Purpose |
| --- | --- | --- |
| `F1_ROOT_DIR` | repo root | Fallback base for data/models |
| `F1_DATA_DIR` | `dataset/` | Dataset directory |
| `F1_MODELS_DIR` | `models/` | Trained model artifacts |

Trained artifacts (`.joblib` + `manifest.json`) are written to `models/`
and are gitignored.

---

## Quickstart

### 1. Command line

Installing the package exposes an `f1-analytics` command:

```powershell
f1-analytics data-status      # shows each expected data file, present/missing
                              #   (never creates or downloads anything)
f1-analytics validate-data    # runs the full validation / drift suite
f1-analytics models-status    # dry-run readiness check for model artifacts
f1-analytics train            # trains finish/dnf/podium/winner artifacts
f1-analytics doctor           # data-status + models-status + query source summary
```

- Missing required data → the CLI prints the exact recovery command.
- `validate-data` and `models-status` exit non-zero on failure, so they are
  safe to use as CI gates.

### 2. Training the models

```powershell
f1-analytics train
```

Trains all four post-qualifying tasks with chronological splits
(train ≤ 2022, validation 2023–2024, test 2025, holdout 2026+).

### 3. Streamlit dashboard

```powershell
streamlit run dashboard/app.py
```

Pages: **Analytics**, **Race Intelligence**, **Drivers**, **Constructors**,
**Circuits**, **LIVE**, **Predictions**, **Coach**, **Assistant**,
**Data Health**.

On the LIVE page, start a session with `openf1` (or `mock` for an offline
demo) and press **Save snapshot as replay** — the snapshot lands in
`dataset/live_replays/` and the `replay` provider can then re-run the
session offline at any time (fully functional without internet or fastf1).

### 4. Tests

Offline smoke tests with a pytest-free runner. Data-dependent tests are
skipped automatically when the local dataset is absent, so the suite also
passes in a clean CI checkout:

```powershell
python tests/run_tests.py
```

or with pytest:

```powershell
python -m pytest tests -q
```

---

## Repository layout

```
src/f1_analytics/   # core package
  analytics/        # driver / constructor / circuit summaries
  assistant/        # LLM race assistant + rule-based fallback
  coach/            # pace & strategy coaching reports
  database/         # SQLite queries against the bundled dataset
  features/         # feature contract definitions
  live/             # live timing providers (OpenF1, Mock, Replay)
  models/           # race prediction artifacts (finish/dnf/podium/winner)
  preprocessing/    # data validation & schemas
  simulation/       # race simulation
dashboard/          # Streamlit app (app.py, intel.py, live_ui.py, skin.py)
dataset/            # local dataset + saved live replay snapshots
models/             # trained model artifacts (gitignored outputs)
tests/              # offline smoke tests
```
