# 4. Station band floors the forecast

Status: accepted, 2026-10-08. Supersedes the 3-hour escalation window in the first PRD.

## Context

The first design trusted the CAMS forecast and let a worse station reading raise only the next 3 hours. The backtest
(`backend/backtest/report.md`, 9 Delhi stations, Oct–Dec 2025) showed CAMS reads about 100 µg/m³ cleaner than the
stations during school hours. The 06:00 email, built from the forecast, caught 30% of Very Poor hours.

## Decision

At build time, the latest station reading no older than `STATION_MAX_AGE_MIN` sets a floor for the rest of the school
day (`STATION_FLOOR_HOURS=24`). Escalation only raises a band, never lowers one.

## Options measured

| Strategy | Very Poor+ hit rate | False alarms |
|---|---|---|
| Forecast only | 30% | 4% |
| Station band as floor (chosen) | 93% | 12% |
| Forecast scaled by station/forecast ratio | 86% | 8% |

## Consequences

- Missing a Very Poor hour sends children out to run in it. An unneeded indoor PE period costs a lesson plan. The floor
  takes more false alarms to miss far fewer bad hours.
- On days when the air clears quickly, the morning brief will be stricter than needed. The live dashboard recomputes
  hourly and shows "Changed since this morning's email".
- A naive persistence baseline scores about the same, so AirDay's value is the decision and the delivery, not a
  better forecast. The pitch says so.
- The station lag is assumed to be 1 hour until it is measured on live data.
