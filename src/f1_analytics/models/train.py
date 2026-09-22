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
DEFAULT_CONTRACT = "post_quali"
_META = {"year", "round", "circuitId"}
PROD_INPUT_COLUMNS = [c for c in FEATURE_COLUMNS
                      if c not in leaking_features(DEFAULT_CONTRACT) and c not in _META]
SEED = 42


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
        return joblib.load(file)

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


def _prep(df: pd.DataFrame, inputs: list[str], medians: dict[str, float]) -> pd.DataFrame:
    """Strategy S1: apply train-fitted medians + missing indicators."""
    X = df[inputs].copy()
    for col in inputs:
        med = medians.get(col, df[col].dropna().median())
        X[col] = df[col].fillna(med)
    for col, is_missing in X.isna().items():
        if is_missing.any():
            X[f"{col}_missing"] = is_missing.astype(int)
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
    X_tr = _prep(train, inputs, medians)
    X_te = _prep(test, inputs, medians)

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


def train_all_years() -> list[Artifact]:
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
        artifact.save()
        artifacts.append(artifact)
    return artifacts


def predictor(task: str) -> Artifact:
    return Artifact.load(task)


def predict_df(artifact: Artifact, df: pd.DataFrame) -> pd.DataFrame:
    """Predict on a DataFrame that has the artifact's input columns."""
    X = _prep(df, artifact.input_columns, artifact.medians)
    if artifact.task == "finish":
        out = np.clip(np.round(artifact.model.predict(X)), 1, 30).astype(int)
        return pd.DataFrame({"finish_pred": out})
    proba = artifact.model.predict_proba(X)[:, 1]
    return pd.DataFrame({"probability": proba})