import type { ActivityRow, Brief, ChatReply, Evaluation, Profile, Rule, RowError } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const KEY_STORAGE = "airday-admin-key";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

// The admin key lives in sessionStorage only: never in the build, cleared when the tab closes.
export function getAdminKey(): string {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(KEY_STORAGE) || "";
}

export function setAdminKey(key: string): void {
  if (key) window.sessionStorage.setItem(KEY_STORAGE, key);
  else window.sessionStorage.removeItem(KEY_STORAGE);
}

async function request<T>(method: string, path: string, opts: { body?: unknown; csv?: string; admin?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: string | undefined;
  if (opts.csv !== undefined) {
    headers["content-type"] = "text/csv";
    body = opts.csv;
  } else if (opts.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (opts.admin) headers["x-admin-key"] = getAdminKey();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body });
  } catch {
    throw new ApiError(0, "Can't reach the AirDay server. Check your connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, (data as { error?: string }).error || `Request failed (${res.status})`, data);
  return data as T;
}

const q = (params: Record<string, string | undefined>) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
  return s ? `?${s}` : "";
};

export const api = {
  school: () => request<Profile>("GET", "/school"),
  updateSchool: (patch: Partial<Profile> & { principalEmail?: string }) =>
    request<Profile>("PUT", "/school", { body: patch, admin: true }),
  activities: () => request<{ activities: ActivityRow[] }>("GET", "/activities"),
  uploadCsv: (csv: string) => request<{ activities: ActivityRow[] }>("PUT", "/activities", { csv, admin: true }),
  sampleCsv: () => request<{ csv: string }>("GET", "/activities/sample"),
  briefLive: (date?: string) => request<Brief>("GET", `/brief/live${q({ date })}`),
  regenerate: (date: string, resend = false) =>
    request<Brief>("POST", `/brief/regenerate${q({ date, resend: resend ? "true" : undefined })}`, { admin: true }),
  replayDates: () => request<{ dates: string[] }>("GET", "/replay/dates"),
  replay: (date: string) => request<Brief>("GET", `/replay${q({ date })}`),
  emailReplay: (date: string) => request<{ sent: boolean }>("POST", `/replay/email${q({ date })}`, { admin: true }),
  evaluate: (p: { type: string; date: string; start: string; end: string; mode: string }) =>
    request<Evaluation>("GET", `/evaluate${q(p)}`),
  chat: (p: { message: string; history: { role: string; content: string }[]; date: string; mode: string }) =>
    request<ChatReply>("POST", "/chat", { body: p }),
  translate: (text: string) =>
    request<{ en: string; hi: string | null; hiValidated: boolean; problems: string[] }>("POST", "/note/translate", {
      body: { text },
      admin: true,
    }),
  rules: () => request<{ version: string; rules: Rule[] }>("GET", "/rules"),
};

export type { RowError };
