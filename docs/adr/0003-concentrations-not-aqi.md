# 3. Decide on concentrations, not hourly AQI

Status: accepted, 2026-10-08

## Context

CPCB defines the National AQI on 24-hour averages. Apps often run hourly values through the same breakpoints and call
the result "AQI". That produces a different number with the same name, which won't match what parents see on SAFAR
or the CPCB site.

## Decision

All timetable decisions use hourly PM2.5 and PM10 concentrations in µg/m³ against the CPCB breakpoints, as half-open
bands. The word "AQI" never appears next to an hourly number; the validator rejects a brief that does. The official
CPCB AQI is shown separately and never feeds a rule.

## Consequences

- Exposure during a 40-minute PE period is what matters, and an hourly concentration describes it.
- Applying 24-hour breakpoints to hourly values is AirDay's own cautious choice. The dashboard says so.
- Two numbers are on screen. The brief explains disagreements in one line ("daily average is Poor; this morning's
  peak is in the Very Poor range").
