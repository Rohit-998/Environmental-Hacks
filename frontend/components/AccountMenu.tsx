"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LogIn, LogOut } from "lucide-react";
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
      <Link href="/signin/" className="btn btn-primary w-full">
        <LogIn aria-hidden="true" /> Sign in
      </Link>
    );
  }
  return (
    <div className="grid gap-1.5">
      <span className="truncate font-semibold text-ink" title={s.label}>
        {s.label}
      </span>
      <button
        type="button"
        className="flex items-center gap-1.5 text-left text-[12px] text-muted hover:text-ink"
        onClick={async () => {
          await signOut();
          window.location.href = "/";
        }}
      >
        <LogOut size={14} aria-hidden="true" /> Sign out
      </button>
    </div>
  );
}
