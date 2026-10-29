"""Dataclass -> dict adapters for coach reports."""

from __future__ import annotations

from f1_analytics.coach.report import CoachReport, Finding


def finding_dict(f: Finding) -> dict:
    return {"area": f.area, "text": f.text, "confidence": f.confidence,
            "conditions": f.conditions}


def report_dict(r: CoachReport) -> dict:
    return {"driver": r.driver, "n_laps": r.n_laps,
            "findings": [finding_dict(f) for f in r.findings],
            "warnings": list(r.warnings), "markdown": r.markdown()}
