"use client";

import { useState, type FormEvent } from "react";

import { ErrorNote, Panel, Pill } from "@/components/Panel";
import { api } from "@/lib/api";

type Answer = {
  question: string;
  answer: string;
  mode: string;
  tools_used: string[];
  evidence_keys: string[];
  audit_id: string;
  live_session: string | null;
};

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chat, setChat] = useState<Answer[]>([]);

  async function askIt(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    try {
      const a = await api<Answer>("/api/assistant/ask", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      setChat((c) => [a, ...c]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="page-title">Race Assistant</h1>
      <p className="page-sub">
        Tool-using race assistant. With an OpenAI-compatible API key it answers with an LLM over tool results; without a
        key it falls back to the built-in rule-based analyser.
      </p>

      <Panel title="Ask a question">
        <form onSubmit={askIt}>
          <div className="row">
            <input
              type="text"
              style={{ flex: 1, minWidth: 280 }}
              placeholder="e.g. How many races has Verstappen won? Which team leads the live session?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button className="btn primary" type="submit" disabled={busy}>
              {busy ? "Thinking..." : "Ask"}
            </button>
          </div>
        </form>
        {error ? <ErrorNote message={error} /> : null}
      </Panel>

      {chat.length > 0 ? (
        <Panel title={`Conversation (${chat.length})`}>
          <div className="chat-list">
            {chat.map((a) => (
              <div className="chat-item" key={a.audit_id}>
                <div className="q">{a.question}</div>
                <div className="a">{a.answer}</div>
                <div className="meta row">
                  <Pill status={a.mode === "llm" ? "ok" : "info"}>{a.mode}</Pill>
                  {(a.tools_used ?? []).map((t) => (
                    <Pill key={t} status="info">{t}</Pill>
                  ))}
                  {a.live_session ? <span className="muted mono">live: {a.live_session}</span> : null}
                  <span className="muted mono">audit {a.audit_id}</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}
    </>
  );
}
