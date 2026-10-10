import type { Metadata, Viewport } from "next";
import { DM_Mono, Manrope } from "next/font/google";
import { Rail } from "@/components/Rail";
import "./globals.css";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope", display: "swap" });
const dmMono = DM_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-dm-mono", display: "swap" });

export const metadata: Metadata = {
  title: "AirDay · Today's air plan for your school",
  description: "Turns the hourly air-pollution forecast into a period-by-period plan for a school's timetable.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f5f7f5" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${manrope.variable} ${dmMono.variable}`}>
      <body className="min-h-screen">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-brand focus:px-3 focus:py-2 focus:text-white"
        >
          Skip to content
        </a>
        <Rail />
        <main id="main" className="workspace">
          {children}
          <footer className="mt-14 border-t border-line pt-5 text-[12px] text-muted">
            Forecast: CAMS via Open-Meteo, a city-area forecast at about 40 km. Station readings: OpenAQ and CPCB.
            Official AQI: CPCB. General guidance based on public advisories, not medical advice.
          </footer>
        </main>
      </body>
    </html>
  );
}
