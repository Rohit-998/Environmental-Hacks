"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BriefView } from "@/components/BriefView";
import { Chat } from "@/components/Chat";
import { api, ApiError } from "@/lib/api";
import { shortDate, todayIST } from "@/lib/bands";
import type { Brief } from "@/lib/types";

export default function TodayPage() {
  const [dates, setDates] = useState<string[]>([]);
  // null until the URL has been read, so the first request is already for the right day.
  const [replay, setReplay] = useState<string | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const latest = useRef(0);

  useEffect(() => {
    api.replayDates().then((r) => setDates(r.dates)).catch(() => setDates([]));
    setReplay(new URLSearchParams(window.location.search).get("replay") ?? "");
  }, []);

  const load = useCallback(async () => {
    if (replay === null) return;
    const id = ++latest.current; // a slower, older request must never overwrite a newer one
    setLoading(true);
    setError("");
    try {
      const b = replay ? await api.replay(replay) : await api.briefLive(todayIST());
      if (id === latest.current) setBrief(b);
    } catch (e) {
      if (id !== latest.current) return;
      setBrief(null);
      setError(e instanceof ApiError ? e.message : "Couldn't load the plan. Check your connection and try again.");
    } finally {
      if (id === latest.current) setLoading(false);
    }
  }, [replay]);

  useEffect(() => {
    load();
  }, [load]);

  function pick(d: string) {
    setReplay(d);
    const url = new URL(window.location.href);
    if (d) url.searchParams.set("replay", d);
    else url.searchParams.delete("replay");
    window.history.replaceState(null, "", url);
  }

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">DAILY AIR PLAN</p>
          <h1>Today&apos;s plan</h1>
          <p className="lede">AirDay checks the hourly air forecast against your outdoor timetable and tells you what to change before the first bell.</p>
        </div>
        <div className="segmented shrink-0" role="group" aria-label="Which day">
          <button type="button" aria-pressed={!replay} onClick={() => pick("")}>
            Today
          </button>
          {dates.map((d) => (
            <button key={d} type="button" aria-pressed={replay === d} onClick={() => pick(d)}>
              {shortDate(d)}
            </button>
          ))}
        </div>
      </header>

      {loading && (
        <div role="status" aria-label="Loading the plan" className="summary-grid">
          <div className="skeleton h-[183px]" />
          <div className="skeleton h-[183px]" />
          <div className="skeleton h-[183px]" />
        </div>
      )}
      {error && (
        <div role="alert" className="notice notice-error">
          <span>{error}</span>
          <button type="button" onClick={load} className="link ml-auto">
            Try again
          </button>
        </div>
      )}
      {brief && !loading && (
        <>
          <BriefView brief={brief} />
          <Chat date={brief.date} mode={brief.mode} />
        </>
      )}
    </>
  );
}
