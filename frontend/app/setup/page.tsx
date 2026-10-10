"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, getAdminKey, setAdminKey } from "@/lib/api";
import { currentSession } from "@/lib/session";
import type { ActivityRow, EmailStatus as EmailStatusT, Me, Profile, RowError } from "@/lib/types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function AdminKey({ onChange }: { onChange: (has: boolean) => void }) {
  const [value, setValue] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // Setup links can carry the key in the URL fragment (#key=...), which is never sent to a server.
    const m = window.location.hash.match(/key=([^&]+)/);
    if (m) {
      setAdminKey(decodeURIComponent(m[1]));
      window.history.replaceState(null, "", window.location.pathname);
    }
    const has = !!getAdminKey();
    setSaved(has);
    onChange(has);
  }, [onChange]);

  return (
    <section className="card">
      <h2 className="font-semibold">Admin key</h2>
      {saved ? (
        <p className="mt-1 flex flex-wrap items-center gap-3 text-sm">
          Key saved for this tab.
          <button type="button" className="underline" onClick={() => { setAdminKey(""); setSaved(false); onChange(false); }}>
            Forget key
          </button>
        </p>
      ) : (
        <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); setAdminKey(value.trim()); setSaved(true); onChange(true); setValue(""); }}>
          <label htmlFor="admin-key" className="sr-only">Admin key</label>
          <input id="admin-key" type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} placeholder="Paste the admin key" className="field mt-0 min-w-0 flex-1" />
          <button type="submit" disabled={!value.trim()} className="btn btn-primary">Save</button>
        </form>
      )}
      <p className="mt-1 text-xs text-muted">Kept in this browser tab only and cleared when you close it.</p>
    </section>
  );
}

function ProfileForm({ canEdit }: { canEdit: boolean }) {
  const [p, setP] = useState<Profile | null>(null);
  const [email, setEmail] = useState("");
  const [query, setQuery] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => { api.school().then(setP).catch(() => {}); }, []);
  if (!p) return <p className="text-muted">Loading school profile…</p>;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!p) return;
    setMsg(null);
    try {
      const patch = { name: p.name, locality: p.locality, lat: Number(p.lat), lon: Number(p.lon), start: p.start, end: p.end, schoolDays: p.schoolDays, ...(email ? { principalEmail: email } : {}) };
      setP(await api.updateSchool(patch));
      setEmail("");
      setMsg({ ok: true, text: "Saved." });
    } catch (err) {
      const errs = err instanceof ApiError ? (err.body.errors as string[] | undefined) : undefined;
      setMsg({ ok: false, text: errs?.join("; ") || (err instanceof Error ? err.message : "Save failed") });
    }
  }

  async function findPlace() {
    // Open-Meteo geocoding finds place names (localities), not street addresses.
    const r = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=1&country=IN`).then((x) => x.json()).catch(() => null);
    const hit = r?.results?.[0];
    if (hit && p) setP({ ...p, locality: [hit.name, hit.admin1].filter(Boolean).join(", "), lat: hit.latitude, lon: hit.longitude });
    else setMsg({ ok: false, text: "No place found. Try a locality name like Rohini or Dwarka." });
  }

  const field = "mt-1 block w-full rounded border border-line px-2 py-1 disabled:bg-gray-50";
  return (
    <form onSubmit={save} className="grid gap-3 card sm:grid-cols-2">
      <h2 className="font-semibold sm:col-span-2">School</h2>
      <label className="text-sm sm:col-span-2">School name<input className={field} disabled={!canEdit} value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} required /></label>
      <div className="text-sm sm:col-span-2">
        <label htmlFor="place">Find your locality</label>
        <div className="mt-1 flex gap-2">
          <input id="place" className="field mt-0 min-w-0 flex-1" disabled={!canEdit} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Rohini" />
          <button type="button" disabled={!canEdit || !query.trim()} onClick={findPlace} className="btn">Find</button>
        </div>
        <p className="mt-1 text-xs text-muted">Using: {p.locality} ({Number(p.lat).toFixed(3)}, {Number(p.lon).toFixed(3)}). The forecast covers the city area, so a nearby locality is enough.</p>
      </div>
      <label className="text-sm">School starts<input type="time" className={field} disabled={!canEdit} value={p.start} onChange={(e) => setP({ ...p, start: e.target.value })} /></label>
      <label className="text-sm">School ends<input type="time" className={field} disabled={!canEdit} value={p.end} onChange={(e) => setP({ ...p, end: e.target.value })} /></label>
      <fieldset className="text-sm sm:col-span-2">
        <legend>School days</legend>
        <div className="mt-1 flex flex-wrap gap-3">
          {DAYS.map((d) => (
            <label key={d} className="flex items-center gap-1">
              <input type="checkbox" disabled={!canEdit} checked={p.schoolDays.includes(d)} onChange={(e) => setP({ ...p, schoolDays: e.target.checked ? [...p.schoolDays, d] : p.schoolDays.filter((x) => x !== d) })} />
              {d}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="text-sm sm:col-span-2">
        Principal email for the 06:00 plan {p.hasEmail && <span className="text-muted">(set; type a new one to change it)</span>}
        <input type="email" className={field} disabled={!canEdit} value={email} onChange={(e) => setEmail(e.target.value)} placeholder={p.hasEmail ? "••••••" : "principal@school.in"} />
      </label>
      {p.hasEmail && <EmailStatus status={p.emailStatus ?? null} canEdit={canEdit} onResent={setP} />}
      <div className="sm:col-span-2">
        <button type="submit" disabled={!canEdit} className="btn btn-primary">Save school</button>
        {msg && <span role={msg.ok ? "status" : "alert"} className={`ml-3 text-sm ${msg.ok ? "text-green-800" : "text-red-800"}`}>{msg.text}</span>}
      </div>
    </form>
  );
}

// While AirDay's AWS account is in the SES sandbox, AWS only delivers to addresses that clicked its verification link.
function EmailStatus({ status, canEdit, onResent }: { status: EmailStatusT; canEdit: boolean; onResent: (p: Profile) => void }) {
  const [busy, setBusy] = useState(false);
  if (status === "verified" || status === "not-checked" || status === null) {
    return status === "verified" ? <p role="status" className="text-sm text-green-800 sm:col-span-2">Email confirmed. The 06:00 plan will arrive here.</p> : null;
  }
  async function resend() {
    setBusy(true);
    try {
      onResent(await api.resendVerification());
    } finally {
      setBusy(false);
    }
  }
  return (
    <div role="status" className="notice sm:col-span-2">
      {status === "pending" ? (
        <>
          <strong>Check your inbox.</strong> Amazon Web Services sent a verification link (subject starts &ldquo;Amazon Web
          Services – Email Address Verification Request&rdquo;). Click it once, and the 06:00 plan starts arriving. Look in
          spam if you don&apos;t see it.
        </>
      ) : (
        <>The verification link expired or failed. Send a new one and click it within 24 hours.</>
      )}
      <button type="button" disabled={!canEdit || busy} onClick={resend} className="ml-2 underline disabled:opacity-50">
        {busy ? "Sending…" : "Send the link again"}
      </button>
    </div>
  );
}

function Timetable({ canEdit }: { canEdit: boolean }) {
  const [rows, setRows] = useState<ActivityRow[]>([]);
  const [csv, setCsv] = useState("");
  const [errors, setErrors] = useState<RowError[]>([]);
  const [msg, setMsg] = useState("");

  useEffect(() => { api.activities().then((r) => setRows(r.activities)).catch(() => {}); }, []);

  async function upload(text: string) {
    setErrors([]);
    setMsg("");
    try {
      const r = await api.uploadCsv(text);
      setRows(r.activities);
      setCsv("");
      setMsg(`Saved ${r.activities.length} activities.`);
    } catch (err) {
      if (err instanceof ApiError && err.body.rowErrors) setErrors(err.body.rowErrors as RowError[]);
      else setMsg(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function useSample() {
    const { csv: sample } = await api.sampleCsv();
    setCsv(sample);
  }

  async function onFile(f: File | undefined) {
    if (f) setCsv(await f.text());
  }

  return (
    <section className="space-y-3 card">
      <h2 className="font-semibold">Outdoor timetable</h2>
      <p className="text-sm text-muted">
        One row per outdoor slot: <code>day,start,end,type,label</code>. Type is assembly, recess or pe. Paste from Excel or upload a CSV.
      </p>
      <label htmlFor="csv" className="sr-only">Timetable CSV</label>
      <textarea id="csv" rows={6} disabled={!canEdit} value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={"Mon,08:40,09:20,pe,Class 6B PE\nMon,10:30,10:50,recess,Recess"} className="w-full rounded border border-line p-2 font-mono text-sm disabled:bg-gray-50" />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={!canEdit || !csv.trim()} onClick={() => upload(csv)} className="btn btn-primary">Save timetable</button>
        <button type="button" disabled={!canEdit} onClick={useSample} className="btn">Use sample timetable</button>
        <label className={`rounded border border-line px-3 py-2 ${canEdit ? "cursor-pointer" : "opacity-50"}`}>
          Upload CSV
          <input type="file" accept=".csv,text/csv,text/plain" disabled={!canEdit} className="sr-only" onChange={(e) => onFile(e.target.files?.[0])} />
        </label>
        <span role="status" className="text-sm text-green-800">{msg}</span>
      </div>
      {errors.length > 0 && (
        <div role="alert" className="notice notice-error">
          <p className="font-semibold">Nothing was saved. Fix these rows and try again:</p>
          <ul className="mt-1 list-disc pl-5">
            {errors.map((e) => <li key={e.line}>Line {e.line}: {e.reason} <code className="text-xs">{e.row}</code></li>)}
          </ul>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Saved outdoor activities</caption>
          <thead><tr className="border-b border-line"><th scope="col">Day</th><th scope="col">Time</th><th scope="col">Type</th><th scope="col">Label</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-line last:border-0"><td className="py-1">{r.day}</td><td>{r.start}–{r.end}</td><td>{r.type}</td><td>{r.label}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CreateSchool({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [place, setPlace] = useState<{ locality: string; lat: number; lon: number } | null>(null);
  const [error, setError] = useState("");

  async function findPlace() {
    const r = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=1&country=IN`).then((x) => x.json()).catch(() => null);
    const hit = r?.results?.[0];
    if (hit) setPlace({ locality: [hit.name, hit.admin1].filter(Boolean).join(", "), lat: hit.latitude, lon: hit.longitude });
    else setError("No place found. Try a locality name like Rohini or Dwarka.");
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.createSchool({ name, ...(place ?? {}) });
      onCreated();
    } catch (err) {
      const errs = err instanceof ApiError ? (err.body.errors as string[] | undefined) : undefined;
      setError(errs?.join("; ") || (err instanceof Error ? err.message : "Couldn't create the school"));
    }
  }

  return (
    <form onSubmit={create} className="space-y-3 card">
      <h2 className="font-semibold">Create your school</h2>
      <label className="block text-sm">
        School name
        <input required className="field" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <div className="text-sm">
        <label htmlFor="new-place">Locality</label>
        <div className="mt-1 flex gap-2">
          <input id="new-place" className="field mt-0 min-w-0 flex-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Dwarka" />
          <button type="button" disabled={!query.trim()} onClick={findPlace} className="btn">
            Find
          </button>
        </div>
        <p className="mt-1 text-xs text-muted">{place ? `Using ${place.locality}` : "Defaults to Rohini, Delhi if you skip this."}</p>
      </div>
      {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
      <button type="submit" disabled={!name.trim()} className="btn btn-primary">
        Create school
      </button>
    </form>
  );
}

export default function SetupPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [demoKey, setDemoKey] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    currentSession().then(async (s) => {
      setSignedIn(s.signedIn);
      setMe(s.signedIn ? await api.me().catch(() => null) : null);
    });
  }, [reload]);

  if (signedIn === null) return <p className="text-muted">Loading…</p>;

  if (signedIn && me && !me.schoolId) {
    return (
      <div className="space-y-5">
        <h1 className="text-[clamp(28px,3.4vw,42px)] font-bold leading-tight tracking-tight">Setup</h1>
        <CreateSchool onCreated={() => setReload((n) => n + 1)} />
      </div>
    );
  }

  const canEdit = signedIn ? true : demoKey;
  return (
    <div className="space-y-5" key={reload}>
      <h1 className="text-[clamp(28px,3.4vw,42px)] font-bold leading-tight tracking-tight">Setup</h1>
      {signedIn ? (
        <p className="text-sm text-muted">Editing your school. Only you can see and change it.</p>
      ) : (
        <>
          <p className="card text-sm">
            This is the shared demo school. <Link href="/signin/" className="underline">Sign in</Link> to set up your own.
          </p>
          <AdminKey onChange={setDemoKey} />
          {!demoKey && <p className="text-sm text-muted">Add the demo admin key to edit the demo school. You can still view everything.</p>}
        </>
      )}
      <ProfileForm canEdit={canEdit} />
      <Timetable canEdit={canEdit} />
    </div>
  );
}
