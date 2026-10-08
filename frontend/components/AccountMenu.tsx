"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { currentSession, onSessionChange, signOut, type Session } from "@/lib/session";

export function AccountMenu() {
  const [s, setS] = useState<Session | null>(null);

  useEffect(() => {
    const load = () => currentSession().then(setS);
    load();
    return onSessionChange(load);
  }, []);

  if (!s) return null;
  if (!s.signedIn) {
    return (
      <Link href="/signin/" className="rounded border border-brand px-2 py-1 text-sm font-semibold text-brand hover:bg-brand hover:text-white">
        Sign in
      </Link>
    );
  }
  return (
    <span className="flex items-center gap-2 text-sm">
      <span className="max-w-[12rem] truncate text-muted" title={s.label}>
        {s.label}
      </span>
      <button
        type="button"
        className="underline"
        onClick={async () => {
          await signOut();
          window.location.href = "/";
        }}
      >
        Sign out
      </button>
    </span>
  );
}
