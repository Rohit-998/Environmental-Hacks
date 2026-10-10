import { authHeaders } from "./session";
import type { ActivityRow, Brief, ChatReply, Evaluation, Me, Profile, Rule, RowError, SafeWindows } from "./types";

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

// Demo admin key: sessionStorage only, never in the build, cleared when the tab closes.
export function getAdminKey(): string {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(KEY_STORAGE) || "";
}

export function setAdminKey(key: string): void {
  if (key) window.sessionStorage.setItem(KEY_STORAGE, key);
  else window.sessionStorage.removeItem(KEY_STORAGE);
}

interface Opts {
  body?: unknown;
  csv?: string;
  // Tenant routes go to /me/... for a signed-in principal and to the public demo school otherwise.
  tenant?: boolean;
}

async function request<T>(method: string, path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: string | undefined;
  if (opts.csv !== undefined) {
    headers["content-type"] = "text/csv";
    body = opts.csv;
  } else if (opts.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let url = path;
  if (opts.tenant || path === "/me" || path.startsWith("/me/")) {
    const auth = await authHeaders();
    if (auth) {
      Object.assign(headers, auth);
      if (opts.tenant) url = `/me${path}`;
    } else if (path.startsWith("/me")) {
      throw new ApiError(401, "Sign in first.");
    } else {
      const key = getAdminKey();
      if (key) headers["x-admin-key"] = key;
    }
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${url}`, { method, headers, body });
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

const T = { tenant: true } as const;

export const api = {
  me: () => request<Me>("GET", "/me"),
  createSchool: (p: Partial<Profile> & { principalEmail?: string }) => request<Profile & { schoolId: string }>("POST", "/me/school", { body: p }),
  school: () => request<Profile>("GET", "/school", T),
  updateSchool: (patch: Partial<Profile> & { principalEmail?: string }) => request<Profile>("PUT", "/school", { ...T, body: patch }),
  resendVerification: () => request<Profile>("POST", "/school/verify-email", T),
  activities: () => request<{ activities: ActivityRow[] }>("GET", "/activities", T),
  uploadCsv: (csv: string) => request<{ activities: ActivityRow[] }>("PUT", "/activities", { ...T, csv }),
  sampleCsv: () => request<{ csv: string }>("GET", "/activities/sample"),
  briefLive: (date?: string) => request<Brief>("GET", `/brief/live${q({ date })}`, T),
  regenerate: (date: string, resend = false) =>
    request<Brief>("POST", `/brief/regenerate${q({ date, resend: resend ? "true" : undefined })}`, T),
  replayDates: () => request<{ dates: string[] }>("GET", "/replay/dates"),
  replay: (date: string) => request<Brief>("GET", `/replay${q({ date })}`, T),
  emailReplay: (date: string) => request<{ sent: boolean }>("POST", `/replay/email${q({ date })}`, T),
  evaluate: (p: { type: string; date: string; start: string; end: string; mode: string }) =>
    request<Evaluation>("GET", `/evaluate${q(p)}`, T),
  safeWindows: (p: { type: string; date: string; duration: string; mode: string; days?: string }) =>
    request<SafeWindows>("GET", `/windows${q(p)}`, T),
  chat: (p: { message: string; history: { role: string; content: string }[]; date: string; mode: string }) =>
    request<ChatReply>("POST", "/chat", { ...T, body: p }),
  translate: (text: string) =>
    request<{ en: string; hi: string | null; hiValidated: boolean; problems: string[] }>("POST", "/note/translate", {
      ...T,
      body: { text },
    }),
  rules: () => request<{ version: string; rules: Rule[] }>("GET", "/rules"),
};

export type { RowError };
