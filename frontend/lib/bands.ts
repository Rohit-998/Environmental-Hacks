import type { Band } from "./types";

// Colour is never the only signal: every use pairs it with the band name as text.
// The tints are light enough to pass WCAG AA (4.5:1) as text on the dark glass panels.
export const bandColor = (band: Band) => `var(--color-band-${band})`;

export const BAND_ORDER: Band[] = ["good", "satisfactory", "moderate", "poor", "very_poor", "severe"];

export const hh = (h: number) => `${String(h).padStart(2, "0")}:00`;

export function todayIST(): string {
  const now = new Date(Date.now() + 5.5 * 3600 * 1000);
  return now.toISOString().slice(0, 10);
}

export function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00+05:30`);
  return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
}

export function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00+05:30`);
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
}
