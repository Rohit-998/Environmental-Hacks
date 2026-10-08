"use client";

import { useCallback, useEffect, useState } from "react";
import { BriefView } from "@/components/BriefView";
import { Chat } from "@/components/Chat";
import { api, ApiError } from "@/lib/api";
import { formatDate, todayIST } from "@/lib/bands";
import type { Brief } from "@/lib/types";

export default function TodayPage() {
  const [dates, setDates] = useState<string[]>([]);
  const [replay, setReplay] = useState<string>("");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.replayDates().then((r) => setDates(r.dates)).catch(() => setDates([]));
    const fromUrl = new URLSearchParams(window.location.search).get("replay");
    if (fromUrl) setReplay(fromUrl);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setBrief(replay ? await api.replay(replay) : await api.briefLive(todayIST()));
    } catch (e) {
      setBrief(null);
      setError(e instanceof ApiError ? e.message : "Something went wrong loading today's plan.");
    } finally {
      setLoading(false);
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted">Daily air plan</p>
          <p className="font-semibold">{replay ? "Replay of a past day" : "Today, live"}</p>
        </div>
        <label className="text-sm">
          <span className="mr-2">View</span>
          <select value={replay} onChange={(e) => pick(e.target.value)} className="rounded border border-line bg-white px-2 py-1">
            <option value="">Today (live)</option>
            {dates.map((d) => (
              <option key={d} value={d}>
                Replay: {formatDate(d)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && (
        <p role="status" className="text-muted">
          Loading the plan…
        </p>
      )}
      {error && (
        <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-800">
          <p>{error}</p>
          <button type="button" onClick={load} className="mt-2 text-sm underline">
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
    </div>
  );
}
