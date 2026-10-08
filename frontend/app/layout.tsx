import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { AccountMenu } from "@/components/AccountMenu";
import "./globals.css";

export const metadata: Metadata = {
  title: "AirDay · Daily air plan for your school",
  description: "Turns the hourly air-pollution forecast into a period-by-period plan for a school timetable.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

const NAV = [
  { href: "/", label: "Today" },
  { href: "/check/", label: "Check an activity" },
  { href: "/setup/", label: "Setup" },
  { href: "/about/", label: "About the data" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:bg-white focus:p-2">
          Skip to content
        </a>
        <header className="border-b border-line bg-white">
          <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-2 px-4 py-3">
            <Link href="/" className="text-lg font-bold text-brand">
              AirDay
            </Link>
            <nav aria-label="Main" className="flex flex-wrap items-center gap-2">
              <ul className="flex flex-wrap gap-1 text-sm">
                {NAV.map((n) => (
                  <li key={n.href}>
                    <Link href={n.href} className="rounded px-2 py-1 text-ink hover:bg-gray-100">
                      {n.label}
                    </Link>
                  </li>
                ))}
              </ul>
              <AccountMenu />
            </nav>
          </div>
        </header>
        <main id="main" className="mx-auto max-w-4xl px-4 py-6">
          {children}
        </main>
        <footer className="mx-auto max-w-4xl px-4 pb-8 text-xs text-muted">
          Forecast: CAMS via Open-Meteo (city-area, about 40 km). Station data: OpenAQ / CPCB. Official AQI: CPCB via
          data.gov.in. General guidance based on public advisories, not medical advice.
        </footer>
      </body>
    </html>
  );
}
