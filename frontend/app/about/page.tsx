"use client";

import { useEffect, useState } from "react";
import { BandBadge } from "@/components/BandBadge";
import { api } from "@/lib/api";
import type { Band, Rule } from "@/lib/types";

const SCOPES = ["assembly", "recess", "pe", "window", "note"] as const;
const SCOPE_NAME: Record<string, string> = { assembly: "Assembly", recess: "Recess", pe: "PE", window: "Windows", note: "Parent note" };
const BAND_ORDER: Band[] = ["good", "satisfactory", "moderate", "poor", "very_poor", "severe", "unknown"];
const BAND_NAME: Record<Band, string> = {
  good: "Good", satisfactory: "Satisfactory", moderate: "Moderate", poor: "Poor",
  very_poor: "Very Poor", severe: "Severe", unknown: "Unknown",
};

export default function AboutPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [version, setVersion] = useState("");

  useEffect(() => {
    api.rules().then((r) => { setRules(r.rules); setVersion(r.version); }).catch(() => {});
  }, []);

  const cell = (band: string, scope: string) => rules.find((r) => r.band === band && r.scope === scope);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">About the data and the rules</h1>

      <section className="space-y-2 rounded-lg border border-line bg-white p-4">
        <h2 className="font-semibold">Two different numbers</h2>
        <p>
          <strong>Hourly PM2.5 and PM10</strong> (µg/m³) drive every recommendation. They come from the CAMS forecast via
          Open-Meteo, which covers the city area at about 40 km per grid cell, so all of Delhi is one or two cells. AirDay
          never claims to know the air at your school gate. CAMS is known to under-predict Delhi&apos;s winter peaks, so
          when the nearest station reads worse than the forecast, AirDay raises the band for the next 3 hours. It never
          lowers one.
        </p>
        <p>
          <strong>The official CPCB AQI</strong> is a 24-hour average. It is shown for reference and never feeds any rule.
          CPCB defines its bands on 24-hour averages; applying them to hourly values is AirDay&apos;s own cautious
          choice, not CPCB&apos;s method. That is why an hourly number is never called &ldquo;AQI&rdquo; here.
        </p>
        <p>
          <strong>GRAP stage</strong> shown is indicative, worked out from the Delhi average AQI. It is not a CAQM order.
          Official orders and school closures always come first.
        </p>
      </section>

      <section className="rounded-lg border border-line bg-white p-4">
        <h2 className="font-semibold">The rules {version && <span className="text-sm font-normal text-muted">(version {version})</span>}</h2>
        <p className="text-sm text-muted">The harder the activity, the earlier it is restricted: PE first, then recess, then assembly.</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <caption className="sr-only">Action for each air band and activity</caption>
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="py-1">Band</th>
                {SCOPES.map((s) => <th key={s} scope="col">{SCOPE_NAME[s]}</th>)}
              </tr>
            </thead>
            <tbody>
              {BAND_ORDER.map((b) => (
                <tr key={b} className="border-b border-line align-top last:border-0">
                  <th scope="row" className="py-2 pr-2"><BandBadge band={b} name={BAND_NAME[b]} /></th>
                  {SCOPES.map((s) => {
                    const r = cell(b, s);
                    if (!r) return <td key={s}>…</td>;
                    const text = r.emit ? r.en.replace(/\{label\} \(\{start\}–\{end\}\): /, "").replace(/\{start\}–\{end\}/, "").replace(/^Windows : /, "") : "Not sent";
                    return (
                      <td key={s} className="py-2 pr-2">
                        <span className="line-clamp-3">{text}</span>
                        <span className="block font-mono text-xs text-muted">{r.id}</span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">
          Sources: CPCB National AQI (2014) health statements, CAQM GRAP schedule, and WHO/EPA guidance on reducing
          exertion during high pollution. Each rule records whether it restates a source or is AirDay&apos;s own reading of it.
        </p>
      </section>
    </div>
  );
}
