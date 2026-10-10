"use client";

import { useEffect, useState } from "react";
import { BandBadge, RuleIds } from "@/components/BandBadge";
import { api, ApiError } from "@/lib/api";
import { hh, todayIST } from "@/lib/bands";
import type { Evaluation } from "@/lib/types";

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function CheckPage() {
  const [base, setBase] = useState(todayIST());
  const [mode, setMode] = useState<"live" | "replay">("live");
  const [dates, setDates] = useState<string[]>([]);
  const [form, setForm] = useState({ type: "pe", date: todayIST(), start: "14:00", end: "15:00" });
  const [result, setResult] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.replayDates().then((r) => setDates(r.dates)).catch(() => {});
  }, []);

  function setContext(v: string) {
    const isReplay = v !== "";
    const b = isReplay ? v : todayIST();
    setMode(isReplay ? "replay" : "live");
    setBase(b);
    setForm((f) => ({ ...f, date: b }));
    setResult(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.evaluate({ ...form, mode }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't check that activity.");
    } finally {
      setBusy(false);
    }
  }

  const options = [0, 1, 2].map((n) => addDays(base, n));

  return (
    <div className="space-y-5">
      <h1 className="text-[clamp(28px,3.4vw,42px)] font-bold leading-tight tracking-tight">Check an activity</h1>
      <p className="text-muted">Planning an event? Check it against the same rules as the morning plan, up to 2 days ahead.</p>

      <form onSubmit={submit} className="grid gap-3 card sm:grid-cols-2">
        <label className="text-sm">
          Plan from
          <select className="field" value={mode === "replay" ? base : ""} onChange={(e) => setContext(e.target.value)}>
            <option value="">Today (live forecast)</option>
            {dates.map((d) => (
              <option key={d} value={d}>
                Replay: {d}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Activity type
          <select className="field" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            <option value="pe">PE, sports day, outdoor event</option>
            <option value="recess">Recess</option>
            <option value="assembly">Assembly</option>
          </select>
        </label>
        <label className="text-sm">
          Day
          <select className="field" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })}>
            {options.map((d, i) => (
              <option key={d} value={d}>
                {i === 0 ? "Today" : i === 1 ? "Tomorrow" : "Day after"} ({d})
              </option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-sm">
            Start
            <input type="time" required className="field" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} />
          </label>
          <label className="text-sm">
            End
            <input type="time" required className="field" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} />
          </label>
        </div>
        <div className="sm:col-span-2">
          <button type="submit" disabled={busy} className="btn btn-primary">
            {busy ? "Checking…" : "Check"}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="notice notice-error">
          {error}
        </p>
      )}

      {result && (
        <section aria-live="polite" className="card">
          <p className="flex flex-wrap items-center gap-2 text-lg font-semibold">
            <BandBadge band={result.band} name={result.bandName} size="lg" />
            {result.text}
            <RuleIds ids={[result.ruleId]} />
          </p>
          <ul className="mt-3 text-sm">
            {result.hours.map((h) => (
              <li key={h.hour}>
                {hh(h.hour)}: PM2.5 {h.pm25 == null ? "unavailable" : `${Math.round(h.pm25)} µg/m³`}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
