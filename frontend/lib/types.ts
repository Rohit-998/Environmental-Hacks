// Mirrors contracts/brief.schema.json. Keep in sync; additive changes only after the schema freeze.

export type Band = "good" | "satisfactory" | "moderate" | "poor" | "very_poor" | "severe" | "unknown";

export interface HourBand {
  hour: number;
  pm25: number | null;
  pm10: number | null;
  band: Band;
  bandName: string;
  forecastBand: Band;
  stationPm25?: number | null;
  stationPm10?: number | null;
  escalated: boolean;
}

export interface Action {
  ruleIds: string[];
  kind: "activity" | "window" | "note";
  activityId: string | null;
  label?: string | null;
  hours: number[];
  band: Band;
  bandName: string;
  change: boolean;
  text: string;
}

export interface Official {
  stationAqi: number | null;
  stationBand?: string | null;
  stationBandName?: string | null;
  stationName?: string | null;
  stationAsOf?: string | null;
  cityAqi: number | null;
  cityBand?: string | null;
  cityBandName?: string | null;
  citySource: "live" | "bulletin";
  cityAsOf?: string | null;
}

export interface Brief {
  schemaVersion: 1;
  rulesVersion: string;
  mode: "live" | "replay";
  date: string;
  weekday: string;
  school?: string;
  schoolDay?: boolean;
  generatedAt: string;
  subject: string;
  headline: string;
  worstBand: Band;
  worstBandName: string;
  official: Official;
  grap: { stage: "I" | "II" | "III" | "IV" | null; kind: "indicative" | "official"; label: string };
  hours: HourBand[];
  actions: Action[];
  parentNote: {
    ruleId: string;
    send: boolean;
    optional: boolean;
    en: string;
    hi: string;
    addition: { en: string; hi: string | null; hiValidated: boolean } | null;
  };
  upstream?: Record<string, string>;
  changedSinceEmail?: { text: string; was: string[]; now: string[] }[];
  emailedAt?: string | null;
}

export interface Me {
  kind: "user" | "demo-admin" | "anonymous";
  schoolId: string | null;
  canWrite: boolean;
  demo: boolean;
}

// "pending" until the principal clicks the AWS verification link (SES sandbox); "not-checked" in local dev.
export type EmailStatus = "verified" | "pending" | "failed" | "not-checked" | null;

export interface Profile {
  name: string;
  locality: string;
  lat: number;
  lon: number;
  start: string;
  end: string;
  schoolDays: string[];
  holidays: string[];
  cpcbStation: string;
  grapOverride: { stage: string; setAt?: string; expiresAt?: string } | null;
  hasEmail: boolean;
  emailStatus?: EmailStatus;
}

export interface ActivityRow {
  id: string;
  day: string;
  start: string;
  end: string;
  type: "assembly" | "recess" | "pe";
  label: string;
}

export interface RowError {
  line: number;
  row: string;
  reason: string;
}

export interface Evaluation {
  type: string;
  date: string;
  start: string;
  end: string;
  band: Band;
  bandName: string;
  ruleId: string;
  change: boolean;
  text: string;
  hours: { hour: number; pm25: number | null; band: Band }[];
}

export interface ChatReply {
  answer: string;
  ruleIds: string[];
  grounded: boolean;
  fixed?: boolean;
}

export interface Rule {
  id: string;
  band: string;
  scope: string;
  change: boolean;
  en: string;
  hi: string;
  basis: "direct" | "derived";
  source: string;
  emit: boolean;
  optional: boolean;
  instruction: string | null;
}
