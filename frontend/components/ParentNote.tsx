"use client";

import { useState } from "react";
import type { Brief } from "@/lib/types";

export function ParentNote({ note, school }: { note: Brief["parentNote"]; school?: string }) {
  const [lang, setLang] = useState<"en" | "hi" | "both">("both");
  const [copied, setCopied] = useState(false);

  if (!note.send) {
    return (
      <section className="rounded-lg border border-line bg-white p-4">
        <h2 className="text-base font-semibold">Parent note</h2>
        <p className="text-sm text-muted">No parent note needed today.</p>
      </section>
    );
  }

  const add = note.addition;
  const en = [note.en, add?.en].filter(Boolean).join("\n");
  const hi = [note.hi, add?.hiValidated ? add.hi : add?.en].filter(Boolean).join("\n");
  const sign = school ? `\n— ${school}` : "";
  const text = lang === "en" ? en + sign : lang === "hi" ? hi + sign : `${en}\n\n${hi}${sign}`;

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section aria-labelledby="note-title" className="rounded-lg border border-line bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id="note-title" className="text-base font-semibold">
          Parent note <span className="font-normal text-muted">({note.optional ? "optional, your call" : "recommended"})</span>
        </h2>
        <div role="group" aria-label="Language" className="flex overflow-hidden rounded border border-line text-sm">
          {(["en", "hi", "both"] as const).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLang(l)}
              aria-pressed={lang === l}
              className={`px-2 py-1 ${lang === l ? "bg-brand text-white" : "bg-white"}`}
            >
              {l === "en" ? "English" : l === "hi" ? "हिंदी" : "Both"}
            </button>
          ))}
        </div>
      </div>
      {lang !== "hi" && <p className="whitespace-pre-line">{en}</p>}
      {lang !== "en" && (
        <p lang="hi" className="mt-2 whitespace-pre-line">
          {hi}
        </p>
      )}
      {add && !add.hiValidated && (
        <p className="mt-2 text-xs text-muted">Your added line is shown in English only: the Hindi translation didn&apos;t pass the check.</p>
      )}
      <button type="button" onClick={copy} className="mt-3 rounded bg-green-700 px-3 py-2 text-sm font-semibold text-white hover:bg-green-800">
        {copied ? "Copied" : "Copy for WhatsApp"}
      </button>
      <span aria-live="polite" className="sr-only">
        {copied ? "Parent note copied" : ""}
      </span>
    </section>
  );
}
