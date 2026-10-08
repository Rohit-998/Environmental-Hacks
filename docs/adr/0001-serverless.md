# 1. Serverless on Lambda, not containers

Status: accepted, 2026-10-08

## Context

The workload is a burst at 06:00 IST (one job per school), then a trickle of dashboard requests during the school
day, then nothing overnight. The team has three days and no operations staff.

## Decision

Lambda for all compute, EventBridge Scheduler for the trigger, SQS between planner and workers, API Gateway HTTP API
in front. One SAM template.

## Consequences

- Cost tracks usage: idle overnight and on weekends costs nothing.
- No servers, patching or cluster to run. Retries, DLQs and concurrency limits are configuration.
- Cold starts add up to a second on the dashboard. Acceptable for a page a principal opens once a morning.
- ECS or EKS would add a container build, a cluster and a load balancer for no benefit at this load profile.
