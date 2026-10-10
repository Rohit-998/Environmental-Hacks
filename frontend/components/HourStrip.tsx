"use client";

import { useState } from "react";
import { bandColor, hh } from "@/lib/bands";
import type { HourBand } from "@/lib/types";

// Column height is capped at 300 µg/m³ so a Severe hour doesn't flatten the rest.
const MAX = 300;

export function HourStrip({ hours, from = 7, to = 14 }: { hours: HourBand[]; from?: number; to?: number }) {
  const [asTable, setAsTable] = useState(false);
  const shown = hours.filter((h) => h.hour >= from && h.hour <= to);
  if (!shown.length) return null;
  const anyEscalated = shown.some((h) => h.escalated);
  // The reading that raised the day: the latest station hour before school with data.
  const trigger = [...hours].reverse().find((h) => h.hour < from && h.stationPm25 != null);

  return (
    <section className="section" aria-labelledby="hours-title">
      <div className="section-title">
        <div>
          <p className="eyebrow">PM2.5 · µg/m³ · CITY-AREA FORECAST</p>
          <h2 id="hours-title">The school day, hour by hour</h2>
          <p className="section-copy">Hourly concentrations, not AQI. Timing is approximate.</p>
        </div>
        <div className="segmented" role="group" aria-label="View">
          <button type="button" aria-pressed={!asTable} onClick={() => setAsTable(false)}>
            Chart
          </button>
          <button type="button" aria-pressed={asTable} onClick={() => setAsTable(true)}>
            Table
          </button>
        </div>
      </div>

      <div className="card">
        {asTable ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[30rem] text-left text-[13px]">
              <thead className="font-mono text-[10px] tracking-wider text-muted">
                <tr className="border-b border-line">
                  <th scope="col" className="py-2 font-normal">HOUR</th>
                  <th scope="col" className="font-normal">FORECAST</th>
                  <th scope="col" className="font-normal">STATION</th>
                  <th scope="col" className="font-normal">BAND USED</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((h) => (
                  <tr key={h.hour} className="border-b border-line last:border-0">
                    <td className="py-2.5 font-mono">{hh(h.hour)}</td>
                    <td>{h.pm25 == null ? "–" : Math.round(h.pm25)}</td>
                    <td>{h.stationPm25 == null ? "–" : Math.round(h.stationPm25)}</td>
                    <td>
                      {h.bandName}
                      {h.escalated && <span className="text-muted"> (raised by the station reading)</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <ol className="grid gap-2" style={{ gridTemplateColumns: `repeat(${shown.length}, minmax(0, 1fr))` }} aria-label="Hourly PM2.5">
            {shown.map((h) => {
              const c = bandColor(h.band);
              const value = h.stationPm25 ?? h.pm25;
              const pct = value == null ? 4 : Math.max(5, Math.min(100, (value / MAX) * 100));
              return (
                <li key={h.hour} className="flex min-w-0 flex-col text-center">
                  <div className="relative h-40 overflow-hidden rounded-md bg-[#f1f5f2]" aria-hidden="true">
                    <div className="absolute inset-x-0 bottom-0 rounded-t-md" style={{ height: `${pct}%`, background: `color-mix(in srgb, ${c} 75%, white)` }} />
                  </div>
                  <span className="mt-2 text-[14px] font-bold">{value == null ? "–" : Math.round(value)}</span>
                  <span className="truncate text-[11px] font-bold" style={{ color: c }}>
                    {h.bandName}
                  </span>
                  <span className="font-mono text-[11px] text-muted">{hh(h.hour)}</span>
                </li>
              );
            })}
          </ol>
        )}
        {anyEscalated && (
          <p className="mt-4 border-t border-line pt-3 text-[12px] text-muted">
            {trigger
              ? `Numbers are the forecast. The nearest station measured ${Math.round(trigger.stationPm25!)} µg/m³ at ${hh(trigger.hour)}, worse than forecast, so the plan treats the rest of the day as ${trigger.bandName}. Forecasts tend to read clean in a Delhi winter.`
              : "The nearest station read worse than the forecast before school, so the plan uses the station's band for the rest of the day."}
          </p>
        )}
      </div>
    </section>
  );
}
