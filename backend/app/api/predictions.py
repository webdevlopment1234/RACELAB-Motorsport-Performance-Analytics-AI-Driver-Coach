"""Model artifacts and prediction endpoints."""

from __future__ import annotations

import pandas as pd
from flask import Blueprint, jsonify, request

from f1_analytics.data import DataNotFoundError
from f1_analytics.models import FeatureSchemaError, ModelArtifactError, models_status, predict_df, predictor

from ..errors import ApiError
from ..json_utils import records, table
from ..services import models_state

bp = Blueprint("predictions", __name__)


@bp.get("/api/models/status")
def models_status_route():
    from f1_analytics import config
    status = models_status()
    return jsonify(status)


@bp.post("/api/models/train")
def train():
    return jsonify(models_state.start_training())


@bp.get("/api/models/train/status")
def train_status():
    return jsonify(models_state.job_status())


@bp.post("/api/predict")
def predict():
    payload = request.get_json(silent=True) or {}
    task = str(payload.get("task", "finish")).strip()
    row = payload.get("row")
    if not isinstance(row, dict) or not row:
        raise ApiError("body must include 'task' and a 'row' object", 400)
    try:
        artifact = predictor(task)
    except ModelArtifactError as exc:
        raise ApiError(str(exc), status=503) from exc
    df = pd.DataFrame([row])
    try:
        scored = predict_df(artifact, df)
    except FeatureSchemaError as exc:
        missing = [c for c in artifact.input_columns if c not in df.columns]
        raise ApiError(f"invalid input row: {exc}", status=400,
                       detail=f"required input columns: {artifact.input_columns}") from exc
    except DataNotFoundError as exc:
        raise ApiError(str(exc), status=503) from exc
    out = {"task": task,
           "input_columns": artifact.input_columns,
           "prediction": records(scored)}
    return jsonify(out)
