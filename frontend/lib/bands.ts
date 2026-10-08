import type { Band } from "./types";

// Colour is never the only signal: every use pairs it with the band name as text.
// Text colours meet WCAG AA (4.5:1) on their background tint.
export const BAND_STYLE: Record<Band, { bg: string; text: string; bar: string }> = {
  good: { bg: "bg-green-50", text: "text-green-800", bar: "bg-green-600" },
  satisfactory: { bg: "bg-lime-50", text: "text-lime-900", bar: "bg-lime-600" },
  moderate: { bg: "bg-yellow-50", text: "text-yellow-900", bar: "bg-yellow-500" },
  poor: { bg: "bg-orange-50", text: "text-orange-900", bar: "bg-orange-600" },
  very_poor: { bg: "bg-red-50", text: "text-red-800", bar: "bg-red-700" },
  severe: { bg: "bg-fuchsia-50", text: "text-fuchsia-900", bar: "bg-fuchsia-900" },
  unknown: { bg: "bg-gray-100", text: "text-gray-800", bar: "bg-gray-400" },
};

export const hh = (h: number) => `${String(h).padStart(2, "0")}:00`;

export function todayIST(): string {
  const now = new Date(Date.now() + 5.5 * 3600 * 1000);
  return now.toISOString().slice(0, 10);
}

export function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00+05:30`);
  return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
}
