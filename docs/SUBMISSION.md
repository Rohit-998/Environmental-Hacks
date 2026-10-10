# AirDay — hackathon submission

**One line:** AirDay reads the hourly air-pollution forecast for a school's locality, checks it against that
school's outdoor timetable, and emails the principal a period-by-period plan at 06:00 IST — what to move indoors
today, and when the air is clear enough to hold it, with a parent note in English and Hindi.

- **Live demo:** https://main.d2ji7br4eqzndl.amplifyapp.com
- **Code:** https://github.com/Rohit-998/Environmental-Hacks
- **Demo video:** _(YouTube link — add after recording)_
- **Track:** Air · **Team:** solo · **Region:** AWS `ap-south-1`

## The problem

On a Delhi winter morning the air is often hazardous before the first bell, yet the school running an outdoor PE
period is the last to know. The number everyone quotes — the official AQI — is a **24-hour average** that lags the
morning badly. A principal has no simple, trustworthy way to decide, period by period, *today*, whether to move
assembly, recess or PE indoors — and no way to find a clean window later in the week for a sports day.

## What AirDay does

- **A 06:00 plan, every school day.** For each school, AirDay snaps to the local forecast, walks that school's
  own timetable, and emails the principal a plan: this assembly proceeds, that PE period moves indoors, from these
  hours, with the reason. A parent note comes ready in English and Hindi.
- **"Find a clear window."** The inverse question: *when can we hold sports day?* AirDay scans the next 3 days
  within school hours and lists the stretches when the air is clear enough — so events get planned into clean air.
- **A grounded assistant.** A chat assistant answers "can we do the 2 pm match tomorrow?" or "when's the next
  clear morning?" using read-only tools over the same rules engine. It can only cite rules the tools actually
  returned — no freelancing about air quality.
- **Replay a real day.** Judges don't need a bad-air day to see it work: replay 19 Nov 2025 (a Severe Delhi
  morning, frozen with real forecast + station + bulletin data) and watch the plan turn red period by period.

## How it decides (and why it's trustworthy)

- Decisions run on **hourly PM2.5/PM10 concentrations**, not the 24-hour AQI — an hourly number is never called
  "AQI". Bands follow CPCB's concentration breakpoints.
- **Rules are data.** 35 rules (7 air bands × 5 activities) live in one `rules.yaml`; the engine, the validator,
  the dashboard and the tests all read it, and every rule cites a health source. A release test blocks shipping if
  any emitted rule cites a source nobody has read.
- **Measured against reality.** A backtest scores the engine against 9 Delhi reference stations (Oct–Dec 2025).
  The forecast alone caught 30% of Very-Poor-or-worse hours; flooring the day at the latest station reading lifts
  that to **93%**. That result is in the repo and re-run in CI.

## Where AWS fits

The whole thing is serverless, one SAM/CloudFormation stack, auto-deployed from GitHub via OIDC (no stored keys):

- **Lambda** — the rules engine, API, planner and worker (Python 3.12).
- **EventBridge Scheduler** → **Lambda planner** → **SQS** (one message per school, DLQ, capped concurrency) →
  **Lambda workers** — the daily fan-out. 1,000 schools in a city cost one forecast fetch, not 1,000, via a shared
  per-grid-cell cache in DynamoDB.
- **API Gateway (HTTP API)** with a **Cognito** JWT authorizer — each principal only ever sees their own school.
- **DynamoDB** single table (on-demand, PITR, TTL). **SES** for the daily email with at-most-once send.
- **SSM Parameter Store** (SecureString) for every secret. **CloudWatch** dashboard + alarms, **X-Ray** tracing,
  **SNS** alarm emails, **AWS Budgets** cost guard, **IAM** least-privilege with a permissions boundary on every
  role. **Amplify Hosting** serves the Next.js dashboard. Built on AWS open source: **Powertools for Lambda** and
  the **Strands Agents SDK**.

Full architecture, data model, reliability and cost: [docs/architecture.md](architecture.md).

## Honest note: Gemini, not Bedrock

The assistant runs on Google Gemini through the Strands Agents SDK — **only because Bedrock model invocation is
blocked on this new AWS account** (every model returns `ValidationException: Operation not allowed`). The agent is
wired for Bedrock (`bedrock:InvokeModel` IAM, a `ModelProvider` deploy switch); switching back is one parameter,
not a code change. Nothing else uses a model — the daily plan, replay and window finder are pure rules.

## Limits (what we're not claiming)

- The forecast is **city-area (~40 km)**, so AirDay never claims to know the air at one gate; it floors the day
  with the nearest station reading and says so.
- SES is in the sandbox, so email only reaches verified addresses (a verification link is built into Setup).
- The Hindi parent-note templates haven't had a native-speaker review yet.

## Tech

Python 3.12 · Next.js 15 (static export) · AWS SAM · GitHub Actions (lint, tests, backtest, build, cfn-lint,
OIDC deploy). 134 backend tests. MIT licensed.

