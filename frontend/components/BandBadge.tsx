import { BAND_STYLE } from "@/lib/bands";
import type { Band } from "@/lib/types";

export function BandBadge({ band, name, size = "sm" }: { band: Band; name: string; size?: "sm" | "lg" }) {
  const s = BAND_STYLE[band] ?? BAND_STYLE.unknown;
  const pad = size === "lg" ? "px-3 py-1 text-base" : "px-2 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${s.bg} ${s.text} ${pad}`}>
      <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-full ${s.bar}`} />
      {name}
    </span>
  );
}

export function RuleIds({ ids }: { ids: string[] }) {
  return (
    <span className="whitespace-nowrap font-mono text-xs text-muted" aria-label={`Rule ${ids.join(", ")}`}>
      [{ids.join(", ")}]
    </span>
  );
}
