import { bandColor } from "@/lib/bands";
import type { Band } from "@/lib/types";

export function BandBadge({ band, name, size = "sm" }: { band: Band; name: string; size?: "sm" | "lg" }) {
  const c = bandColor(band);
  const pad = size === "lg" ? "px-2.5 py-1 text-[13px]" : "px-2 py-0.5 text-[11px]";
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded font-bold ${pad}`}
      style={{ color: c, background: `color-mix(in srgb, ${c} 10%, white)` }}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full" style={{ background: c }} />
      {name}
    </span>
  );
}

export function RuleIds({ ids }: { ids: string[] }) {
  return (
    <span className="inline-flex flex-wrap gap-1" aria-label={`Rule ${ids.join(", ")}`}>
      {ids.map((id) => (
        <span key={id} className="rule-id">
          {id}
        </span>
      ))}
    </span>
  );
}
