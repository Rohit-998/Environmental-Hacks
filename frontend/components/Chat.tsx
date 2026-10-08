"use client";

import { useState } from "react";
import { RuleIds } from "./BandBadge";
import { api, ApiError } from "@/lib/api";

interface Msg {
  role: "user" | "assistant";
  content: string;
  ruleIds?: string[];
  grounded?: boolean;
}

const SUGGESTIONS = ["Can we hold sports day tomorrow afternoon?", "Is recess outdoors okay today?", "When is the air best today?"];

export function Chat({ date, mode }: { date: string; mode: "live" | "replay" }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setError("");
    setBusy(true);
    const history = msgs.slice(-6).map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: message }]);
    setInput("");
    try {
      const r = await api.chat({ message, history, date, mode });
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, ruleIds: r.ruleIds, grounded: r.grounded }]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The assistant is unavailable right now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="chat-title" className="rounded-lg border border-line bg-white p-4">
      <h2 id="chat-title" className="text-base font-semibold">
        Ask about the next 2 days
      </h2>
      <p className="text-sm text-muted">Answers come from the same rules as the plan and cite a rule ID.</p>

      <ul className="mt-3 space-y-2" aria-live="polite">
        {msgs.map((m, i) => (
          <li key={i} className={m.role === "user" ? "text-right" : ""}>
            <span className={`inline-block max-w-[90%] rounded-lg px-3 py-2 text-left ${m.role === "user" ? "bg-brand text-white" : "bg-gray-100"}`}>
              {m.content}
              {m.ruleIds && m.ruleIds.length > 0 && (
                <span className="ml-1">
                  <RuleIds ids={m.ruleIds} />
                </span>
              )}
              {m.grounded === false && <span className="block text-xs text-muted">Shown from the rules directly.</span>}
            </span>
          </li>
        ))}
        {busy && (
          <li role="status" className="text-sm text-muted">
            Checking the forecast…
          </li>
        )}
      </ul>

      {msgs.length === 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" onClick={() => send(s)} className="rounded-full border border-line px-3 py-1 text-sm hover:bg-gray-50">
              {s}
            </button>
          ))}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-800">
          {error}
        </p>
      )}

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Your question
        </label>
        <input
          id="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={500}
          placeholder="e.g. Can Class 7 go outside at 11:00?"
          className="min-w-0 flex-1 rounded border border-line px-3 py-2"
        />
        <button type="submit" disabled={busy || !input.trim()} className="rounded bg-brand px-4 py-2 font-semibold text-white disabled:opacity-50">
          Ask
        </button>
      </form>
    </section>
  );
}
