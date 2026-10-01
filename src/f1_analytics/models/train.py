"""Model training, evaluation, and artifact persistence.

Targets come from training_dataset.parquet: finish (regression),
is_dnf / is_podium / is_winner (classification; winner scored at the
race level). Splits are chronological by year. Null handling is
Strategy S1: train-only median imputation + missing indicators.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)

from .. import config
from ..features import leaking_features, split_years, training_table
from ..preprocessing import FEATURE_COLUMNS, TARGETS

# Inputs are the leak-free features at POST-QUALIFYING time. post_race
# features (e.g. pit_stop_avg_ms) are excluded per the Phase 3 audit;
# meta columns (year/round/circuitId) are not trainable features.
DEFAULT_CONTRACT = config.MODEL_CONTRACT
_META = {"year", "round", "circuitId"}
PROD_INPUT_COLUMNS = [c for c in FEATURE_COLUMNS
                      if c not in leaking_features(DEFAULT_CONTRACT) and c not in _META]


class ModelArtifactError(RuntimeError):
    """Raised when a model artifact is missing, incompatible, or unreadable."""


class FeatureSchemaError(ValueError):
    """Raised when a scoring frame is missing expected feature columns."""


SEED = config.MODEL_SEED


def _train_command() -> str:
    return "f1-analytics train"


@dataclass
class Artifact:
    task: str
    model: Any = None
    metrics: dict[str, float] = field(default_factory=dict)
    medians: dict[str, float] = field(default_factory=dict)
    indicator_cols: list[str] = field(default_factory=list)
    input_columns: list[str] = field(default_factory=list)
    train_years: tuple[int, int] | None = None
    val_years: tuple[int, int] | None = None
    test_years: tuple[int, int] | None = None
    split: str = DEFAULT_CONTRACT
    null_strategy: str = "S1_impute_indicators"
    data_version: str = "5,094 x 31 (training_dataset.parquet)"
    seed: int = SEED

    def save(self, directory: Path | None = None) -> Path:
        path = directory or config.MODELS_DIR
        path.mkdir(parents=True, exist_ok=True)
        file = path / f"{self.task}.joblib"
        joblib.dump(self, file)
        return file

    @classmethod
    def load(cls, task: str, directory: Path | None = None) -> "Artifact":
        file = (directory or config.MODELS_DIR) / f"{task}.joblib"
        if not file.exists():
            raise ModelArtifactError(
                f"Model artifact missing for task {task!r}: {file}\n\n"
                f"Train it with `{_train_command()}` (requires "
                f"training_dataset.parquet), then retry."
            )
        try:
            obj = joblib.load(file)
        except Exception as exc:  # noqa: BLE001 - any pickle/environment issue
            raise ModelArtifactError(
                f"Model artifact for task {task!r} exists but could not be loaded: {file}\n"
                f"Reason: {type(exc).__name__}: {exc}\n\n"
                "This usually means the artifact was trained with a different "
                "numpy/scikit-learn version (pickle is not portable across major "
                "versions). Re-train it in this environment with "
                f"`{_train_command()}` so version checks match."
            ) from exc
        if not isinstance(obj, cls):
            raise ModelArtifactError(
                f"{file} is not a model artifact (found {type(obj).__name__}). "
                f"Re-train with `{_train_command()}`."
            )
        if obj.task != task:
            raise ModelArtifactError(
                f"{file} contains task {obj.task!r}, expected {task!r}. "
                f"Re-train with `{_train_command()}`."
            )
        return obj

    def validate(self, expected_columns: list[str] | None = None) -> tuple[bool, list[str]]:
        """Check the artifact is internally consistent and matches the expected
        production feature schema. Returns (ok, messages)."""
        problems: list[str] = []
        if self.task not in config.MODEL_TASKS:
            problems.append(f"unknown task {self.task!r}")
        if self.model is None:
            problems.append("artifact has no fitted model")
        if not self.input_columns:
            problems.append("artifact has no input_columns recorded")
        if expected_columns is not None:
            expected = set(expected_columns)
            actual = set(self.input_columns)
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing:
                problems.append(f"missing expected input columns: {missing}")
            if extra:
                problems.append(f"unexpected extra input columns: {extra}")
        if not self.data_version:
            problems.append("artifact has no data_version recorded")
        if self.split != DEFAULT_CONTRACT:
            problems.append(f"split contract {self.split!r} != {DEFAULT_CONTRACT!r}")
        model = self.model
        if model is not None and hasattr(model, "feature_names_in_"):
            expected = list(self.input_columns) + list(self.indicator_cols)
            fitted = list(model.feature_names_in_)
            if fitted != expected:
                problems.append(
                    "fitted model feature set does not match artifact schema "
                    f"(model has {len(fitted)} features, expected {len(expected)}; "
                    "re-train with `f1-analytics train`)"
                )
        elif self.indicator_cols:
            problems.append(
                "artifact records missing indicators but the fitted model has no "
                "feature_names_in_ metadata; re-train with `f1-analytics train`"
            )
        return (not problems), problems

    @classmethod
    def from_parts(cls, task: str, model: Any, input_columns: list[str],
                   metrics: dict[str, float] | None = None,
                   medians: dict[str, float] | None = None,
                   indicator_cols: list[str] | None = None,
                   **kwargs: Any) -> "Artifact":
        """Construct an artifact from already-prepared components (used by tests
        to build incompatible artifacts deliberately)."""
        return cls(
            task=task, model=model, metrics=metrics or {},
            medians=medians or {}, indicator_cols=indicator_cols or [],
            input_columns=input_columns, **kwargs,
        )

    def to_json(self) -> str:
        return json.dumps({
            "task": self.task,
            "metrics": self.metrics,
            "input_columns": self.input_columns,
            "train_years": self.train_years,
            "val_years": self.val_years,
            "test_years": self.test_years,
            "split": self.split,
            "null_strategy": self.null_strategy,
            "data_version": self.data_version,
            "seed": self.seed,
        }, indent=2)


def _fit_imputation(df: pd.DataFrame, inputs: list[str]) -> tuple[dict[str, float], list[str]]:
    """Median per input (train only) + missing indicator columns."""
    medians: dict[str, float] = {}
    indicator_cols: list[str] = []
    for col in inputs:
        if df[col].isna().any():
            med = df[col].dropna().median()
            medians[col] = float(med) if not pd.isna(med) else 0.0
            indicator_cols.append(f"{col}_missing")
    return medians, indicator_cols


def _prep(
    df: pd.DataFrame,
    inputs: list[str],
    medians: dict[str, float],
    indicator_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Strategy S1: train-fitted medians + missing indicators (same layout as inference)."""
    X = df[inputs].copy()
    missing = X.isna()
    for col in inputs:
        med = medians.get(col)
        if med is None:
            med = X[col].dropna().median()
            med = float(med) if not pd.isna(med) else 0.0
        X[col] = X[col].fillna(med)
    for col in indicator_cols or []:
        if not col.endswith("_missing"):
            continue
        base = col[: -len("_missing")]
        if base in missing.columns:
            X[col] = missing[base].astype(int)
    return X


def _expected_calibration_error(y_true: np.ndarray, proba: np.ndarray, bins: int = 10) -> float:
    bin_edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for i in range(bins):
        m = (proba >= bin_edges[i]) & (proba < bin_edges[i + 1])
        if m.sum() == 0:
            continue
        acc = y_true[m].mean()
        conf = proba[m].mean()
        ece += m.sum() * abs(acc - conf)
    return ece / len(proba)


def race_level_metrics(df_test: pd.DataFrame, probs: np.ndarray) -> dict[str, float]:
    """Winner is a race-level ranking problem: rank drivers per race by p(win)."""
    tmp = df_test[["year", "round", "raceId", "is_winner"]].copy()
    tmp["prob"] = probs
    tmp = tmp.sort_values(["raceId", "prob"], ascending=[True, False])
    top1 = tmp.groupby("raceId").head(1)
    top1_acc = float(top1["is_winner"].mean())
    tmp["rank"] = tmp.groupby("raceId").cumcount() + 1
    winner_rank = tmp[tmp["is_winner"] == 1].groupby("raceId")["rank"].min()
    mrr = float(winner_rank.mean()) if len(winner_rank) else 0.0
    return {"race_top1_acc": top1_acc, "avg_winner_rank": mrr,
            "n_races": int(df_test["raceId"].nunique())}


def _classifier_metrics(y_test: pd.Series, proba: np.ndarray) -> dict[str, float]:
    preds = (proba >= 0.5).astype(int)
    y = np.asarray(y_test)
    metrics = {
        "f1": float(f1_score(y, preds, zero_division=0)),
        "accuracy": float(accuracy_score(y, preds)),
        "brier": float(brier_score_loss(y, proba)),
        "ece": float(_expected_calibration_error(y, proba)),
    }
    if len(np.unique(y)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y, proba))
    return metrics


def train_for_target(task: str, train: pd.DataFrame, test: pd.DataFrame,
                     inputs: list[str] | None = None) -> Artifact:
    inputs = inputs or PROD_INPUT_COLUMNS
    medians, indicator_cols = _fit_imputation(train, inputs)
    X_tr = _prep(train, inputs, medians, indicator_cols)
    X_te = _prep(test, inputs, medians, indicator_cols)

    if task == "finish":
        y_tr = train["finish"].astype(int)
        y_te = test["finish"].astype(int)
        baseline = DummyRegressor(strategy="median").fit(X_tr, y_tr)
        model = HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.08, random_state=SEED)
        model.fit(X_tr, y_tr)
        pred = np.clip(np.round(model.predict(X_te)), 1, len(test) + 10)
        base_pred = np.clip(np.round(baseline.predict(X_te)), 1, len(test) + 10)
        artifact = Artifact(task=task, model=model, input_columns=inputs,
                            indicator_cols=indicator_cols, medians=medians)
        artifact.metrics = {
            "mae": float(mean_absolute_error(y_te, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_te, pred))),
            "spearman": float(pd.Series(pred).corr(pd.Series(y_te.values), method="spearman")),
            "baseline_median_mae": float(mean_absolute_error(y_te, base_pred)),
            "baseline_grid_mae": float(mean_absolute_error(y_te, test["grid_position"])),
        }
        return artifact

    y_tr = train[task].astype(int)
    y_te = test[task].astype(int)
    base_rate = float(y_tr.mean())
    dummy = DummyClassifier(strategy="prior").fit(X_tr, y_tr)
    if y_tr.nunique() > 1:
        model = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.08, random_state=SEED, max_leaf_nodes=31)
        model.fit(X_tr, y_tr)
    else:
        model = dummy
    proba = model.predict_proba(X_te)[:, 1]
    artifact = Artifact(task=task, model=model, input_columns=inputs,
                        indicator_cols=indicator_cols, medians=medians)
    artifact.metrics = _classifier_metrics(y_te, proba)
    artifact.metrics["base_rate"] = base_rate
    artifact.metrics["baseline_prior_f1"] = _classifier_metrics(
        y_te, dummy.predict_proba(X_te)[:, 1])["f1"]
    if task == "is_winner":
        artifact.metrics.update(race_level_metrics(test, proba))
    return artifact


def train_all_years(output_dir: Path | None = None, save: bool = True) -> list[Artifact]:
    df = training_table()
    train, val, test, holdout = split_years(
        df, config.TRAIN_MAX_YEAR, config.VAL_YEARS, config.TEST_YEARS
    )
    artifacts = []
    for task in TARGETS:
        artifact = train_for_target(task, train, test)
        artifact.train_years = (config.TRAIN_MAX_YEAR, max(config.VAL_YEARS + config.TEST_YEARS))
        artifact.val_years = config.VAL_YEARS
        artifact.test_years = config.TEST_YEARS
        if save:
            artifact.save(output_dir)
            _write_manifest(artifact, output_dir or config.MODELS_DIR)
        artifacts.append(artifact)
    return artifacts


def _write_manifest(artifact: Artifact, directory: Path) -> None:
    """Write models/.manifest.json with the exact schema the artifact expects,
    so a future reader can reject incompatible artifacts early."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        manifest_path = directory / "manifest.json"
        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest[str(artifact.task)] = {
            "task": artifact.task,
            "input_columns": sorted(artifact.input_columns),
            "data_version": artifact.data_version,
            "split": artifact.split,
            "seed": artifact.seed,
            "train_years": list(artifact.train_years) if artifact.train_years else None,
            "val_years": list(artifact.val_years) if artifact.val_years else None,
            "test_years": list(artifact.test_years) if artifact.test_years else None,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 - manifest is best-effort metadata
        pass


def ensure_models(directory: Path | None = None) -> list[Artifact]:
    """Train all model artifacts if any expected artifact is missing, and
    validate the result. Raises if the training table itself is unavailable."""
    expected = [f"{t}.joblib" for t in TARGETS]
    target_dir = directory or config.MODELS_DIR
    missing = [f for f in expected if not (target_dir / f).exists()]
    if not missing:
        return [predictor(t, target_dir) for t in TARGETS]
    return train_all_years(output_dir=target_dir, save=True)


def predictor(task: str, directory: Path | None = None) -> Artifact:
    return Artifact.load(task, directory)


def models_status(directory: Path | None = None) -> dict[str, Any]:
    """Non-raising readiness report for every model task.

    Returns {"ok": bool, "models": {task: {...status...}}}. Never raises on
    missing/incompatible artifacts.
    """
    target_dir = directory or config.MODELS_DIR
    out: dict[str, Any] = {"ok": True, "models": {}}
    for task in config.MODEL_TASKS:
        file = target_dir / f"{task}.joblib"
        if not file.exists():
            out["models"][task] = {
                "ok": False,
                "path": str(file),
                "reason": "missing",
                "error": f"no artifact at {file}",
            }
            out["ok"] = False
            continue
        try:
            artifact = Artifact.load(task, target_dir)
            valid, problems = artifact.validate(PROD_INPUT_COLUMNS)
            out["models"][task] = {
                "ok": valid,
                "path": str(file),
                "reason": "ok" if valid else "invalid",
                "error": "; ".join(problems) if problems else "",
                "input_columns": artifact.input_columns,
                "data_version": artifact.data_version,
                "split": artifact.split,
                "seed": artifact.seed,
            }
            if not valid:
                out["ok"] = False
        except ModelArtifactError as exc:
            out["models"][task] = {
                "ok": False,
                "path": str(file),
                "reason": "unreadable",
                "error": str(exc),
            }
            out["ok"] = False
    return out


def _prep_predict(df: pd.DataFrame, artifact: "Artifact") -> pd.DataFrame:
    """Apply the exact training-time imputation schema (Strategy S1).

    Indicator columns are always rebuilt from artifact.indicator_cols so the
    inference frame has the identical feature set the model was trained on,
    regardless of which columns happen to be missing in this frame.
    """
    inputs = artifact.input_columns
    X = df[inputs].copy()
    missing = X.isna()
    for col in inputs:
        med = artifact.medians.get(col)
        if med is not None:
            X[col] = X[col].fillna(med)
        else:
            X[col] = X[col].fillna(X[col].dropna().median())
    for col in artifact.indicator_cols:
        if not col.endswith("_missing"):
            continue
        base = col[: -len("_missing")]
        if base in X.columns:
            X[col] = missing[base].astype(int)
    return X


def predict_df(artifact: Artifact, df: pd.DataFrame) -> pd.DataFrame:
    """Predict on a DataFrame that has the artifact's input columns.

    Raises FeatureSchemaError with an actionable message if required feature
    columns are missing or are not numeric.
    """
    if artifact.model is None:
        raise ModelArtifactError(
            f"Artifact for task {artifact.task!r} has no fitted model. "
            f"Re-train with `{_train_command()}`."
        )
    if df is None or df.empty:
        raise FeatureSchemaError(
            "Nothing to predict: the scoring frame is empty.\n\n"
            "The Predictions page builds a scoring row from the training table; "
            "if you are calling predict_df() directly, pass a DataFrame with the "
            "expected feature columns."
        )
    expected = set(artifact.input_columns)
    missing = sorted(expected - set(df.columns))
    if missing:
        raise FeatureSchemaError(
            f"Scoring frame is missing {len(missing)} of {len(expected)} required "
            f"input columns: {missing}. Details:\n"
            f"  expected schema (task {artifact.task!r}, data_version "
            f"{artifact.data_version!r}): {sorted(expected)}\n"
            f"  provided columns: {sorted(df.columns)}\n\n"
            "Update the scoring input to match the artifact's feature contract "
            f"(see `{_train_command()}` and models/models-status)."
        )
    for col in artifact.input_columns:
        if not pd.api.types.is_numeric_dtype(df[col].dtype):
            raise FeatureSchemaError(
                f"Feature column {col!r} must be numeric for prediction, but it is "
                f"{df[col].dtype} (task {artifact.task!r}). Convert the column to a "
                "numeric type (missing values are fine - they are imputed) and retry."
            )
    X = _prep_predict(df, artifact)
    if artifact.task == "finish":
        out = np.clip(np.round(artifact.model.predict(X)), 1, 30).astype(int)
        return pd.DataFrame({"finish_pred": out})
    proba = artifact.model.predict_proba(X)[:, 1]
    return pd.DataFrame({"probability": proba})