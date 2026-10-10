"use client";

import { useState } from "react";
import { LoaderCircle, SendHorizontal } from "lucide-react";
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
      setError(e instanceof ApiError ? e.message : "The assistant is unavailable right now. The plan above still holds.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section" aria-labelledby="chat-title">
      <div className="section-title">
        <div>
          <p className="eyebrow">PLANNING AHEAD</p>
          <h2 id="chat-title">Ask about the next two days</h2>
          <p className="section-copy">Answers come from the same rules as the plan and name the rule they used.</p>
        </div>
      </div>

      <div className="card">
        {msgs.length > 0 && (
          <ul className="mb-4 grid gap-3" aria-live="polite">
            {msgs.map((m, i) => (
              <li key={i} className={m.role === "user" ? "flex justify-end" : "flex"}>
                <div className={`max-w-[85%] rounded-lg px-4 py-2.5 text-[14px] ${m.role === "user" ? "bg-brand text-white" : "border border-line bg-[#f7faf8]"}`}>
                  <p>{m.content}</p>
                  {m.ruleIds && m.ruleIds.length > 0 && (
                    <div className="mt-2">
                      <RuleIds ids={m.ruleIds} />
                    </div>
                  )}
                  {m.grounded === false && <p className="mt-1 text-[12px] text-muted">Shown from the rules directly.</p>}
                </div>
              </li>
            ))}
          </ul>
        )}
        {busy && (
          <p role="status" className="mb-3 flex items-center gap-2 text-[13px] text-muted">
            <LoaderCircle size={15} className="animate-spin" aria-hidden="true" /> Checking the forecast
          </p>
        )}
        {msgs.length === 0 && (
          <div className="mb-4 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" onClick={() => send(s)} className="rounded-md border border-line bg-[#f7faf8] px-3 py-1.5 text-[13px] font-semibold text-[#26362e] hover:border-[#c9d7ce] hover:bg-white">
                {s}
              </button>
            ))}
          </div>
        )}
        {error && (
          <p role="alert" className="notice notice-error mb-3">
            {error}
          </p>
        )}
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <label htmlFor="chat-input" className="sr-only">
            Your question
          </label>
          <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} maxLength={500} placeholder="Can Class 7 go outside at 11:00?" className="field mt-0 flex-1" />
          <button type="submit" disabled={busy || !input.trim()} className="btn btn-primary">
            <SendHorizontal aria-hidden="true" /> Ask
          </button>
        </form>
      </div>
    </section>
  );
}
