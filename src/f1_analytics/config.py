import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if raw:
        return Path(raw).expanduser().resolve()
    return default


# Paths resolve to the repository root on an editable install. All data
# locations can be overridden with environment variables so the package
# also works from a wheel / different working directory:
#   F1_ROOT_DIR  - repository root (fallback for data/models dirs)
#   F1_DATA_DIR  - dataset/ directory
#   F1_MODELS_DIR - models/ directory
ROOT_DIR = _env_path("F1_ROOT_DIR", Path(__file__).resolve().parents[2])
DATA_DIR = _env_path("F1_DATA_DIR", ROOT_DIR / "dataset")
KAGGLE_DIR = DATA_DIR / "kaggledataset"
HUGGINGFACE_DIR = DATA_DIR / "huggingface"
F1_DB_PATH = HUGGINGFACE_DIR / "f1.db"
TRAINING_DATASET = HUGGINGFACE_DIR / "training_dataset.parquet"
DRIVER_PROFILES = HUGGINGFACE_DIR / "driver_profiles.parquet"
TRACKS_YAML = HUGGINGFACE_DIR / "tracks.yaml"
LIVE_REPLAYS_DIR = DATA_DIR / "live_replays"

MODELS_DIR = _env_path("F1_MODELS_DIR", ROOT_DIR / "models")

# Model tasks + lifecycle constants (Phase 4)
MODEL_TASKS = ("finish", "is_dnf", "is_podium", "is_winner")
MODEL_CONTRACT = "post_quali"
MODEL_SEED = 42

# Chronological splits (Phase 4)
TRAIN_MAX_YEAR = 2022
VAL_YEARS = (2023, 2024)
TEST_YEARS = (2025,)
HOLDOUT_YEARS = (2026,)

# Live timing (Phase 7)
LIVE_PROVIDER = "openf1"  # openf1 | mock | replay
OPENF1_BASE_URL = "https://api.openf1.org/v1"
OPENF1_TIMEOUT = 10
OPENF1_POLL_SECONDS = 5.0
OPENF1_MAX_RETRIES = 3

# Assistant (Phase 11)
ASSISTANT_API_KEY_ENV = "F1_ASSISTANT_API_KEY"
ASSISTANT_BASE_URL_ENV = "F1_ASSISTANT_BASE_URL"
ASSISTANT_MODEL = "gpt-4o-mini"
ASSISTANT_TIMEOUT = 30.0
ASSISTANT_MAX_RETRIES = 2
ASSISTANT_LOGS_DIR = ROOT_DIR / "database" / "assistant_logs"