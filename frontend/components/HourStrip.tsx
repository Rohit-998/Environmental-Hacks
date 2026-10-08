"use client";

import { useState } from "react";
import { BAND_STYLE, hh } from "@/lib/bands";
import type { HourBand } from "@/lib/types";

// Bar height is capped at 300 µg/m³ so a Severe hour doesn't flatten the rest.
const MAX = 300;

export function HourStrip({ hours, from = 7, to = 14 }: { hours: HourBand[]; from?: number; to?: number }) {
  const [asTable, setAsTable] = useState(false);
  const shown = hours.filter((h) => h.hour >= from && h.hour <= to);
  if (!shown.length) return <p className="text-sm text-muted">No hourly data for school hours.</p>;

  return (
    <section aria-labelledby="hours-title" className="rounded-lg border border-line bg-white p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="hours-title" className="text-base font-semibold">
          Hour by hour (PM2.5, µg/m³, city-area forecast)
        </h2>
        <button type="button" onClick={() => setAsTable(!asTable)} className="text-sm text-brand underline" aria-pressed={asTable}>
          {asTable ? "Show chart" : "Show as table"}
        </button>
      </div>

      {asTable ? (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line">
              <th scope="col" className="py-1">Hour</th>
              <th scope="col">Forecast PM2.5</th>
              <th scope="col">Station PM2.5</th>
              <th scope="col">Band used</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((h) => (
              <tr key={h.hour} className="border-b border-line last:border-0">
                <td className="py-1">{hh(h.hour)}</td>
                <td>{h.pm25 ?? "–"}</td>
                <td>{h.stationPm25 ?? "–"}</td>
                <td>
                  {h.bandName}
                  {h.escalated && " (escalated from station reading)"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <ol className="grid gap-1" style={{ gridTemplateColumns: `repeat(${shown.length}, minmax(0, 1fr))` }} aria-label="Hourly PM2.5">
          {shown.map((h) => {
            const s = BAND_STYLE[h.band] ?? BAND_STYLE.unknown;
            const pct = h.pm25 == null ? 6 : Math.max(6, Math.min(100, (h.pm25 / MAX) * 100));
            const station = h.stationPm25 == null ? null : Math.min(100, (h.stationPm25 / MAX) * 100);
            return (
              <li key={h.hour} className="flex flex-col items-center text-center">
                <div className="relative flex h-28 w-full items-end justify-center rounded bg-gray-50" aria-hidden="true">
                  <div className={`w-3/4 rounded-t ${s.bar}`} style={{ height: `${pct}%` }} />
                  {station != null && (
                    <div className="absolute left-1 right-1 border-t-2 border-dashed border-ink" style={{ bottom: `${station}%` }} />
                  )}
                </div>
                <span className="mt-1 text-xs font-semibold">{h.pm25 == null ? "–" : Math.round(h.pm25)}</span>
                <span className={`text-[11px] leading-tight ${s.text}`}>
                  {h.bandName}
                  {h.escalated ? "*" : ""}
                </span>
                <span className="text-[11px] text-muted">{hh(h.hour)}</span>
              </li>
            );
          })}
        </ol>
      )}
      <p className="mt-2 text-xs text-muted">
        Dashed line: nearest station reading. * Band raised because the station reading was worse than the forecast. Hourly
        values are concentrations, not AQI. Timing is approximate.
      </p>
    </section>
  );
}
