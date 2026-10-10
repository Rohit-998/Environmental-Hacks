import { BandBadge, RuleIds } from "./BandBadge";
import { HourStrip } from "./HourStrip";
import { ParentNote } from "./ParentNote";
import { formatDate } from "@/lib/bands";
import type { Action, Brief } from "@/lib/types";

// "Morning assembly (07:50–08:10): hold indoors." -> time, what, instruction. Falls back to the whole text.
function splitAction(text: string): { time?: string; what: string; instruction: string } {
  const m = text.match(/^(.*?)\s*\((\d{2}:\d{2})[–-](\d{2}:\d{2})\):\s*(.*)$/);
  if (m) return { time: `${m[2]}–${m[3]}`, what: m[1], instruction: m[4] };
  const w = text.match(/^Windows (\d{2}:\d{2})[–-](\d{2}:\d{2}):\s*(.*)$/);
  if (w) return { time: `${w[1]}–${w[2]}`, what: "Windows", instruction: w[3] };
  return { what: text, instruction: "" };
}

function ActionRow({ a }: { a: Action }) {
  const s = splitAction(a.text);
  return (
    <div className="table-row" role="listitem">
      <span className="time">{s.time ?? "All day"}</span>
      <span className="font-bold">{s.what}</span>
      <span className="text-[13px] text-[#45564d]">{s.instruction}</span>
      <span className="row-rules flex flex-wrap items-center justify-end gap-1.5">
        <BandBadge band={a.band} name={a.bandName} />
        <RuleIds ids={a.ruleIds} />
      </span>
    </div>
  );
}

function ActionTable({ rows }: { rows: Action[] }) {
  return (
    <div className="table" role="list">
      <div className="table-head" aria-hidden="true">
        <span>TIME</span>
        <span>ACTIVITY</span>
        <span>WHAT TO DO</span>
        <span className="text-right">BAND · RULE</span>
      </div>
      {rows.map((a, i) => (
        <ActionRow key={i} a={a} />
      ))}
    </div>
  );
}

export function BriefView({ brief }: { brief: Brief }) {
  const changes = brief.actions.filter((a) => a.change && a.kind !== "note");
  const same = brief.actions.filter((a) => !a.change && a.kind !== "note");
  const noTimetable = !brief.actions.some((a) => a.kind === "activity");
  const n = changes.length;
  const o = brief.official;

  return (
    <>
      <div className="mb-5 grid gap-2.5 empty:hidden">
        {brief.mode === "replay" && (
          <p role="note" className="notice">
            Replay of {formatDate(brief.date)}: the plan as it looked at 06:00 that day, from archived forecasts and measured station data.
          </p>
        )}
        {noTimetable && (
          <p role="note" className="notice">
            No outdoor activities on the timetable for {brief.weekday}.{" "}
            <a href="/setup/" className="link">
              Add your timetable
            </a>{" "}
            to get a plan for assembly, recess and PE.
          </p>
        )}
        {brief.schoolDay === false && (
          <p role="note" className="notice">
            {formatDate(brief.date)} is not a school day, so no email goes out. The plan below is for reference.
          </p>
        )}
        {!!brief.changedSinceEmail?.length && (
          <p role="note" className="notice">
            Changed since this morning&apos;s email: {brief.changedSinceEmail.map((c) => c.text).join("; ")}
          </p>
        )}
      </div>

      <section className="summary-grid" aria-label="Today at a glance">
        <article className="card card-forest">
          <span className="card-label">Today&apos;s decision</span>
          <strong className="card-value">{n ? `${n} change${n === 1 ? "" : "s"} today` : "No changes today"}</strong>
          <p className="card-note">{brief.headline}</p>
          <div className="mt-4">
            <span className="inline-flex items-center gap-1.5 rounded bg-white/10 px-2.5 py-1 text-[12px] font-bold text-white">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full" style={{ background: "#9ce6b6" }} />
              Worst hour: {brief.worstBandName}
            </span>
          </div>
        </article>
        <article className="card">
          <span className="card-label">Delhi AQI ({o.citySource === "bulletin" ? "CPCB bulletin" : "station average"})</span>
          <strong className="card-value">{o.cityAqi ?? "—"}</strong>
          <p className="card-note">{o.cityAqi != null ? `${o.cityBandName}${o.cityAsOf ? ` · ${o.cityAsOf}` : ""}` : "Unavailable right now"}. A 24-hour average, shown for reference only.</p>
        </article>
        <article className="card">
          <span className="card-label">GRAP stage</span>
          <strong className="card-value">{brief.grap.stage ?? "None"}</strong>
          <p className="card-note">{brief.grap.kind === "official" ? "Set from a CAQM order." : "Indicative, from the Delhi AQI. Not a CAQM order."}</p>
        </article>
      </section>

      <section className="section" aria-labelledby="changes-title">
        <div className="section-title">
          <div>
            <p className="eyebrow">{formatDate(brief.date).toUpperCase()}</p>
            <h2 id="changes-title">{n ? "What changes today" : "Everything runs as normal"}</h2>
            <p className="section-copy">Every line names the rule behind it, so you can check why.</p>
          </div>
          <span className={brief.mode === "replay" ? "badge-data sample" : "badge-data"}>{brief.mode === "replay" ? "Replay" : "Live data"}</span>
        </div>
        {n > 0 && <ActionTable rows={changes} />}
        {same.length > 0 && (
          <details className="mt-3" open={!n}>
            <summary className="cursor-pointer py-2 text-[13px] font-bold text-muted hover:text-ink">As normal ({same.length})</summary>
            <div className="mt-2">
              <ActionTable rows={same} />
            </div>
          </details>
        )}
      </section>

      <HourStrip hours={brief.hours} />
      <ParentNote note={brief.parentNote} school={brief.school} />

      <p className="mt-6 font-mono text-[11px] text-muted">
        Built {brief.generatedAt.slice(11, 16)} IST · rules {brief.rulesVersion}
        {brief.upstream && <> · {Object.entries(brief.upstream).map(([k, v]) => `${k} ${v}`).join(", ")}</>}
      </p>
    </>
  );
}
