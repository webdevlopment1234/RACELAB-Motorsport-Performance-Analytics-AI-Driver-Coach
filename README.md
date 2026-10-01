# F1 Analytics — RACELAB

Motorsport performance analytics and AI driver coach. Historical race
analytics, live timing, pace/strategy coaching, race prediction, and an
LLM-powered race assistant.

The package uses [PEP 621] metadata in `pyproject.toml` as the source of
truth for dependencies and optional extras.

[PEP 621]: https://peps.python.org/pep-0621/

## Requirements

- Python 3.10+
- Optional: internet (live data / LLM feature calls). Everything else
  runs fully offline against the bundled local database.

## Installation

Create and activate a virtual environment, then install the profile you
need. All pins (versions + extras) live in `pyproject.toml`.

### Core (everything that works offline)

```powershell
pip install -e .
```

or, equivalently, via the requirements file:

```powershell
pip install -r requirements.txt
```

### Live timing (fastf1)

```powershell
pip install -e .[live]
```

Adds `fastf1>=3.8` for telemetry-aware live timing. The default live
provider (`OpenF1`, free, no API key) and the offline `Mock`/`Replay`
providers do **not** require `fastf1`.

### AI / LLM assistant (openai)

```powershell
pip install -e .[assistant]
```

Adds `openai>=1.30`. Without an API key the assistant falls back to a
built-in rule-based analyser, so the package works even if this extra is
not installed.

### Development / tests

```powershell
pip install -e .[dev]
```

Installs core + `pytest>=8.0`.

### All extras

```powershell
pip install -e .[live,assistant,dev]
```

## Configuration

Configuration lives in `src/f1_analytics/config.py`. Assistant settings
are read from environment variables:

| Variable                   | Default      | Purpose                       |
| -------------------------- | ------------ | ----------------------------- |
| `F1_ASSISTANT_API_KEY`     | *(empty)*    | OpenAI API key for assistant  |
| `F1_ASSISTANT_BASE_URL`    | *(empty)*    | Optional custom API base URL  |

Without a key, the assistant uses its rule-based fallback. Secrets can be
placed in a `.env` file (loaded via `python-dotenv`); `.gitignore`
ignores `.streamlit/secrets.toml` for Streamlit deployment secrets.

## Quickstart

### Command-line tools (CLI)

Installing the package exposes a `f1-analytics` command for checking data
and model readiness without touching the dashboard:

```powershell
f1-analytics data-status      # shows each expected data file, present/missing
                              #   (never creates or downloads anything)
f1-analytics validate-data    # runs the full validation / drift-suite suite
f1-analytics models-status    # dry-run readiness check for model artifacts
f1-analytics train            # trains finish/dnf/podium/winner artifacts (models/)
f1-analytics doctor           # data-status + models-status + query source summary
```

- Missing required data → the CLI prints the exact recovery command.
- `validate-data` and `models-status` exit non-zero when checks fail, so
  they are safe to use as CI gates.
- Trained artifacts (`.joblib` + `manifest.json`) are written to `models/`
  (override with `F1_MODELS_DIR`) and are gitignored.

### Streamlit dashboard

```powershell
streamlit run dashboard/app.py
```

Pages: Race Intelligence, Analytics, Drivers, Constructors, Circuits,
LIVE, Predictions, Coach, Assistant, Data Health. Race Intelligence is
the flagship screen: live/historical race view with timing P1-P4, a
track map, telemetry gauges, a speed/throttle/brake/gear/delta trace,
tyre strategy, and the AI driver coach. Fully functional offline.

### Tests

Offline smoke tests (pytest-free runner). Data-dependent tests are skipped
automatically when the local dataset is absent, so the suite also runs in a
clean CI checkout:

```powershell
python tests/run_tests.py
```

or with pytest:

```powershell
python -m pytest tests -q
```

## Repository layout

```
src/f1_analytics/   # core package
  analytics/        # driver / constructor / circuit summaries
  assistant/        # LLM race assistant + rule-based fallback
  coach/            # pace & strategy coaching reports
  database/         # SQLite queries against bundled dataset
  features/         # feature contract definitions
  live/             # live timing providers (OpenF1, Mock, Replay)
  models/           # race prediction
  preprocessing/    # data validation & schemas
  simulation/       # race simulation
dashboard/          # Streamlit app
tests/              # offline smoke tests
```