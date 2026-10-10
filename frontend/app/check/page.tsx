"use client";

import { useEffect, useState } from "react";
import { BandBadge, RuleIds } from "@/components/BandBadge";
import { api, ApiError } from "@/lib/api";
import { hh, todayIST } from "@/lib/bands";
import type { Evaluation, SafeWindows } from "@/lib/types";

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

const TYPE_NAME: Record<string, string> = { pe: "PE / sports / events", recess: "recess", assembly: "assembly" };

function SafeWindowFinder({ mode, base }: { mode: "live" | "replay"; base: string }) {
  const [type, setType] = useState("pe");
  const [duration, setDuration] = useState("2");
  const [result, setResult] = useState<SafeWindows | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // The context (today vs a replay day) is chosen in the form above; changing it clears stale results.
  useEffect(() => { setResult(null); setError(""); }, [mode, base]);

  async function find() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.safeWindows({ type, date: base, duration, mode, days: "3" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't find windows.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 card">
      <div>
        <h2 className="text-lg font-semibold">Find a clear window</h2>
        <p className="text-sm text-muted">
          Planning a sports day or an outdoor event? AirDay scans the next 3 days and shows when the air is clear
          enough to hold it during school hours — the same rules as the morning plan.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">
          Activity
          <select className="field" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="pe">PE, sports day, outdoor event</option>
            <option value="recess">Recess</option>
            <option value="assembly">Assembly</option>
          </select>
        </label>
        <label className="text-sm">
          Needs
          <select className="field" value={duration} onChange={(e) => setDuration(e.target.value)}>
            <option value="1">1 hour</option>
            <option value="2">2 hours</option>
            <option value="3">3 hours</option>
          </select>
        </label>
        <div className="flex items-end">
          <button type="button" onClick={find} disabled={busy} className="btn btn-primary">
            {busy ? "Scanning…" : "Find windows"}
          </button>
        </div>
      </div>
      {error && <p role="alert" className="notice notice-error">{error}</p>}
      {result && (
        <div aria-live="polite" className="space-y-3">
          {result.days.map((day) => (
            <div key={day.date} className="rounded border border-line p-3">
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                {day.weekday} {day.date}
                {!day.schoolDay && <span className="font-normal text-muted">· no school</span>}
              </p>
              {day.windows.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {day.windows.map((w) => (
                    <li key={w.start} className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-mono">{w.start}–{w.end}</span>
                      <BandBadge band={w.band} name={w.bandName} />
                      <span className="text-muted">clear for {TYPE_NAME[type]}</span>
                      <RuleIds ids={[w.ruleId]} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-muted">
                  {day.hasForecast
                    ? `No clear ${duration}-hour window during school hours.`
                    : "Forecast not available this far out."}
                </p>
              )}
            </div>
          ))}
          <p className="text-xs text-muted">
            Windows cover whole clear hours inside school hours ({result.schoolStart}–{result.schoolEnd}). A window
            means no change is recommended; the band shows how clean it is.
          </p>
        </div>
      )}
    </section>
  );
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

      <SafeWindowFinder mode={mode} base={base} />
    </div>
  );
}
