"""Race assistant (LLM + rule-based fallback)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from f1_analytics.assistant.assistant import ask

from ..errors import ApiError
from ..services.live_state import session as live_session

bp = Blueprint("assistant", __name__)


@bp.post("/api/assistant/ask")
def assistant_ask():
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        raise ApiError("body must include 'question'", 400)
    answer = ask(question)
    return jsonify({
        "question": answer.question,
        "answer": answer.answer,
        "mode": answer.mode,
        "tools_used": answer.tools_used,
        "evidence_keys": answer.evidence_keys,
        "audit_id": answer.audit_id,
        "live_session": live_session.name(),
    })
