# 6. Fan-out through SQS with a shared forecast cache

Status: accepted, 2026-10-08. Replaces the single scheduled Lambda in the first build.

## Context

A single scheduled Lambda that loops over schools works for one school and fails badly for many: one slow upstream
call delays everyone, one failure aborts the run, and the 15-minute Lambda limit caps the number of schools. Each
school also fetched its own forecast, although CAMS Global is 0.4° and a whole city falls in one or two grid cells.

## Decision

- The planner snaps every school to its CAMS grid cell, fetches each cell's forecast once into a shared `CACHE`
  partition, then sends one SQS message per school.
- Workers process batches of 10 with `ReportBatchItemFailures`, so only failed schools are retried. After 3 receives
  a message moves to the DLQ, which alarms.
- Workers are idempotent: the brief write overwrites, and the email claim allows one send per school per day.

## Consequences

- Upstream calls scale with cities, not schools.
- A failing school is isolated and visible; the others still get their email on time.
- Reserved concurrency (20) bounds the load on SES and upstream APIs.
- One more moving part (the queue) than a loop. Worth it for isolation and retries that come for free.
