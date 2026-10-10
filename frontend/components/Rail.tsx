"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpenText, CalendarCheck, ClipboardCheck, SlidersHorizontal, Sun } from "lucide-react";
import { AccountMenu } from "./AccountMenu";
import { API_URL } from "@/lib/api";

const NAV = [
  { href: "/", label: "Today's plan", icon: CalendarCheck },
  { href: "/check/", label: "Check an activity", icon: ClipboardCheck },
  { href: "/setup/", label: "School setup", icon: SlidersHorizontal },
  { href: "/about/", label: "Data and rules", icon: BookOpenText },
];

/** The rail's status line is read from /health, not asserted: a status that can't report a problem is decoration. */
function SystemStatus() {
  const [state, setState] = useState<"checking" | "ok" | "down">("checking");
  useEffect(() => {
    let live = true;
    fetch(`${API_URL}/health`)
      .then((r) => live && setState(r.ok ? "ok" : "down"))
      .catch(() => live && setState("down"));
    return () => {
      live = false;
    };
  }, []);
  const label = state === "checking" ? "Checking…" : state === "ok" ? "Operational" : "Unreachable";
  return (
    <div className="rail-status">
      <span className="status-dot" style={state === "down" ? { background: "#d17a73", boxShadow: "none" } : undefined} />
      <span>
        API status<strong>{label}</strong>
      </span>
    </div>
  );
}

export function Rail() {
  const path = usePathname() || "/";
  const norm = (p: string) => (p.endsWith("/") ? p : `${p}/`);
  return (
    <aside className="rail">
      <Link className="brand" href="/" aria-label="AirDay home">
        <span className="brand-mark" aria-hidden="true">
          <Sun size={18} strokeWidth={2.4} />
        </span>
        <span>
          <strong>AirDay</strong>
          <small>School air planning</small>
        </span>
      </Link>
      <nav className="rail-nav" aria-label="Main">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = norm(path) === norm(href);
          return (
            <Link key={href} href={href} className={active ? "nav-item active" : "nav-item"} aria-current={active ? "page" : undefined}>
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="rail-bottom">
        <AccountMenu />
        <SystemStatus />
      </div>
    </aside>
  );
}
