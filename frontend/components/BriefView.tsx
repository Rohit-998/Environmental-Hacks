import { BandBadge, RuleIds } from "./BandBadge";
import { HourStrip } from "./HourStrip";
import { ParentNote } from "./ParentNote";
import { formatDate } from "@/lib/bands";
import type { Action, Brief } from "@/lib/types";

function ActionItem({ a }: { a: Action }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 border-b border-line py-2 last:border-0">
      <span>{a.text}</span>
      <span className="flex items-center gap-2">
        <BandBadge band={a.band} name={a.bandName} />
        <RuleIds ids={a.ruleIds} />
      </span>
    </li>
  );
}

function OfficialPanel({ brief }: { brief: Brief }) {
  const o = brief.official;
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-3">
      <div className="rounded-lg border border-line bg-white p-3">
        <dt className="text-muted">Official CPCB AQI{o.stationName ? `, ${o.stationName}` : ""}</dt>
        <dd className="mt-1 text-lg font-semibold">
          {o.stationAqi != null ? (
            <>
              {o.stationAqi} <span className="text-sm font-normal">{o.stationBandName}</span>
            </>
          ) : (
            <span className="text-base font-normal text-muted">Unavailable</span>
          )}
        </dd>
        <dd className="text-xs text-muted">24-hour rolling{o.stationAsOf ? `, as of ${o.stationAsOf}` : ""}</dd>
      </div>
      <div className="rounded-lg border border-line bg-white p-3">
        <dt className="text-muted">Delhi AQI ({o.citySource === "bulletin" ? "CPCB bulletin" : "average of stations"})</dt>
        <dd className="mt-1 text-lg font-semibold">
          {o.cityAqi != null ? (
            <>
              {o.cityAqi} <span className="text-sm font-normal">{o.cityBandName}</span>
            </>
          ) : (
            <span className="text-base font-normal text-muted">Unavailable</span>
          )}
        </dd>
        <dd className="text-xs text-muted">{o.cityAsOf ? `As of ${o.cityAsOf}` : "Display only, never used in the rules"}</dd>
      </div>
      <div className="rounded-lg border border-line bg-white p-3">
        <dt className="text-muted">GRAP</dt>
        <dd className="mt-1 font-semibold">{brief.grap.stage ? `Stage ${brief.grap.stage}` : "No stage"}</dd>
        <dd className="text-xs text-muted">{brief.grap.label}</dd>
      </div>
    </dl>
  );
}

export function BriefView({ brief }: { brief: Brief }) {
  const changes = brief.actions.filter((a) => a.change && a.kind !== "note");
  const same = brief.actions.filter((a) => !a.change && a.kind !== "note");

  return (
    <div className="space-y-5">
      {brief.mode === "replay" && (
        <p role="note" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <strong>REPLAY: {formatDate(brief.date)}.</strong> Runs the plan as of 06:00 on that day, on archived forecast
          data. Live forecasts can be less precise.
        </p>
      )}
      {!brief.actions.some((a) => a.kind === "activity") && (
        <p role="note" className="rounded-lg border border-line bg-white p-3 text-sm">
          No outdoor activities on the timetable for {brief.weekday}.{" "}
          <a href="/setup/" className="font-semibold underline">
            Add your timetable
          </a>{" "}
          to get a plan for assembly, recess and PE.
        </p>
      )}
      {brief.schoolDay === false && (
        <p role="note" className="rounded-lg border border-line bg-white p-3 text-sm">
          {formatDate(brief.date)} is not a school day, so no email goes out. The plan below is for reference.
        </p>
      )}

      <section aria-labelledby="decision" className="rounded-lg border border-line bg-white p-4">
        <p className="text-sm text-muted">{formatDate(brief.date)}</p>
        <h1 id="decision" className="mt-1 text-xl font-bold sm:text-2xl">
          {changes.length ? `${changes.length} change${changes.length === 1 ? "" : "s"} today` : "No changes today"}
        </h1>
        <p className="mt-1 flex flex-wrap items-center gap-2">
          <BandBadge band={brief.worstBand} name={brief.worstBandName} size="lg" />
          <span>{brief.headline}</span>
        </p>
        {!!brief.changedSinceEmail?.length && (
          <p className="mt-3 rounded bg-amber-50 p-2 text-sm text-amber-900">
            Changed since this morning&apos;s email: {brief.changedSinceEmail.map((c) => c.text).join(" · ")}
          </p>
        )}
      </section>

      <section aria-labelledby="changes-title" className="rounded-lg border border-line bg-white p-4">
        <h2 id="changes-title" className="text-base font-semibold">
          {changes.length ? "What changes today" : "Everything runs as normal"}
        </h2>
        {changes.length > 0 && <ul className="mt-1">{changes.map((a, i) => <ActionItem key={i} a={a} />)}</ul>}
        {same.length > 0 && (
          <details className="mt-3" open={!changes.length}>
            <summary className="cursor-pointer text-sm font-semibold text-muted">As normal ({same.length})</summary>
            <ul className="mt-1">{same.map((a, i) => <ActionItem key={i} a={a} />)}</ul>
          </details>
        )}
      </section>

      <ParentNote note={brief.parentNote} school={brief.school} />
      <OfficialPanel brief={brief} />
      <HourStrip hours={brief.hours} />

      <p className="text-xs text-muted">
        Generated {brief.generatedAt.slice(11, 16)} IST · rules {brief.rulesVersion}
        {brief.upstream &&
          " · data: " +
            Object.entries(brief.upstream)
              .map(([k, v]) => `${k} ${v}`)
              .join(", ")}
      </p>
    </div>
  );
}
