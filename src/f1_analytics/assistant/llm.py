"""Pluggable LLM client with a rule-based no-key fallback (Phase 11)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .. import config

REDACTED = "***"


@dataclass
class LLMClient:
    provider: str = "openai"
    model: str = config.ASSISTANT_MODEL
    key: str | None = field(default_factory=lambda: os.getenv(config.ASSISTANT_API_KEY_ENV))
    base_url: str | None = field(default_factory=lambda: os.getenv(config.ASSISTANT_BASE_URL_ENV))

    @property
    def available(self) -> bool:
        return bool(self.key)

    def complete(self, system: str, user: str) -> str | None:
        """Return the model answer, or None if no key / provider unavailable."""
        if not self.available:
            return None
        try:
            if self.provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=self.key, base_url=self.base_url)
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    max_tokens=600,
                )
                return resp.choices[0].message.content
        except Exception as exc:  # noqa: BLE001
            # never leak the key or traceback into a user answer
            return f"[provider unavailable: {type(exc).__name__}]"
        return None


def run_rule_based(question: str, evidence: dict[str, Any], tools_used: list[str]) -> str:
    """Deterministic answer from tool output only (works offline)."""
    from ..analytics import driver_summary_table
    q = question.lower()
    topics: list[str] = []
    if any(w in q for w in ("win", "wins", "victor", "champion")):
        topics.append("recent win leaders")
    if any(w in q for w in ("monaco", "circuit", "location", "won at")):
        topics.append("circuit winners")
    if any(w in q for w in ("constructor", "team", "manufacturer")):
        topics.append("constructor standings")
    if any(w in q for w in ("live", "leader", "position", "current", "now")):
        topics.append("live status")
    if any(w in q for w in ("coach", "review", "pace", "sector")):
        topics.append("coach")
    if any(w in q for w in ("sql", "query", "count", "average", "table", "select")):
        topics.append("sql")
    if not topics:
        topics.append("general")
    lines = []
    if "sql" in topics and evidence.get("sql_query"):
        sql = evidence["sql_query"]
        if sql.get("success") and sql.get("value"):
            if isinstance(sql["value"], list) and sql["value"]:
                first = sql["value"][0]
                if isinstance(first, dict):
                    lines.append("Query result (first 10 rows):")
                    for row in sql["value"][:10]:
                        lines.append(f"- {row}")
                else:
                    lines.append(f"Query result: {sql['value'][:10]}")
            else:
                lines.append(f"Query result: {sql.get('value')}")
        else:
            lines.append(f"Query was not executed: {sql.get('value')}")
    if "coach" in topics and evidence.get("coach"):
        report = evidence["coach"]["value"]
        if report.get("findings"):
            lines.append("Coach findings:")
            for f in report["findings"]:
                lines.append(f"- {f.get('area')}: {f.get('text')} (confidence "
                             f"{f.get('confidence', 0):.0%})")
        else:
            lines.append(f"Coach report has no findings ({report.get('warnings', ['n/a'])}).")
    if "live status" in topics and evidence.get("live_status"):
        st = evidence["live_status"]["value"]
        if st.get("is_live"):
            lines.append("Live status: race in progress.")
            for row in st.get("leaderboard", [])[:10]:
                lines.append(f"  P{row.get('position')} {row.get('name_acronym')}")
            lines.append(f"Data source {st.get('source')}, fetched {st.get('fetched_at')}.")
        else:
            lines.append("No live feed available right now.")
    if "recent win leaders" in topics:
        try:
            df = driver_summary_table()
            top = df.head(10)[["driver", "wins"]]
            lines.append("Career win leaders (all-time):")
            for _, r in top.iterrows():
                lines.append(f"- {r['driver']}: {int(r['wins'])} wins")
        except Exception:  # noqa: BLE001
            lines.append("Win-leader data unavailable (coverage gap).")
    if not lines:
        lines.append("I need more specific coverage. I can answer about driver wins, "
                     "constructor stats, circuit winners, live standings, or coaching findings - "
                     "all sourced from validated local / live data.")
    lines.insert(0, f"[rule-based answer] Topic: {', '.join(topics)}")
    lines.append(f"Tools used: {', '.join(tools_used) or 'none'}")
    return "\n".join(lines)