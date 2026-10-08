# 2. Single-table DynamoDB

Status: accepted, 2026-10-08

## Context

Every access is by school and date: read a profile, read a timetable, write a brief, claim an email. There are no
cross-tenant queries except the planner's school list and the shared forecast cache.

## Decision

One on-demand table keyed `PK`/`SK`. Tenant data under `SCHOOL#<id>`; two shared partitions, `REGISTRY` and `CACHE`.
The email claim is a conditional update on `EMAIL#<date>`.

## Consequences

- Every read is a `GetItem` or a single-partition `Query`. No scans, no joins, predictable latency at any size.
- The conditional write gives at-most-once email without a separate lock service.
- TTL clears the cache and counters for free.
- Ad hoc reporting across schools needs an export (S3 export or a stream), not SQL. Acceptable: there is no
  reporting requirement yet.
- RDS would need a VPC, connection pooling from Lambda and a running instance for a workload that is idle most of the day.
