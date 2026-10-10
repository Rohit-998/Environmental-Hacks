"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import type { Brief } from "@/lib/types";

const LANGS = [
  { id: "en", label: "English" },
  { id: "hi", label: "हिंदी" },
  { id: "both", label: "Both" },
] as const;

export function ParentNote({ note, school }: { note: Brief["parentNote"]; school?: string }) {
  const [lang, setLang] = useState<"en" | "hi" | "both">("both");
  const [copied, setCopied] = useState(false);

  const add = note.addition;
  const en = [note.en, add?.en].filter(Boolean).join("\n");
  const hi = [note.hi, add?.hiValidated ? add.hi : add?.en].filter(Boolean).join("\n");
  const sign = school ? `\n${school}` : "";
  const text = lang === "en" ? en + sign : lang === "hi" ? hi + sign : `${en}\n\n${hi}${sign}`;

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section className="section" aria-labelledby="note-title">
      <div className="section-title">
        <div>
          <p className="eyebrow">FOR PARENTS</p>
          <h2 id="note-title">Parent note</h2>
          <p className="section-copy">
            {!note.send ? "The air doesn't call for a note today." : note.optional ? "Optional today: your call." : "Recommended today. Paste it into the class WhatsApp groups."}
          </p>
        </div>
        {note.send && (
          <div className="segmented" role="group" aria-label="Language">
            {LANGS.map((l) => (
              <button key={l.id} type="button" onClick={() => setLang(l.id)} aria-pressed={lang === l.id}>
                {l.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {note.send && (
        <div className="card">
          <div className="grid gap-4 text-[15px]">
            {lang !== "hi" && <p className="max-w-[70ch] whitespace-pre-line">{en}</p>}
            {lang !== "en" && (
              <p lang="hi" className="max-w-[70ch] whitespace-pre-line">
                {hi}
              </p>
            )}
          </div>
          {add && !add.hiValidated && <p className="mt-3 text-[12px] text-muted">Your added line stays in English: its Hindi translation didn&apos;t pass the check.</p>}
          <div className="mt-5 flex items-center gap-3 border-t border-line pt-4">
            <button type="button" onClick={copy} className="btn btn-primary">
              {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
              {copied ? "Copied" : "Copy for WhatsApp"}
            </button>
            <span aria-live="polite" className="sr-only">
              {copied ? "Parent note copied" : ""}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
