# AirDay

**Daily air-safety plans for school timetables.** AirDay reads the hourly PM2.5/PM10 forecast for a school's
locality, checks it against that school's outdoor timetable — assembly, recess, PE — and emails the principal a
period-by-period plan at **06:00 IST**: what to move indoors today, with a parent note in English and Hindi. Every
recommendation carries a rule ID traceable to a cited health source.

Built for the [WeMakeDevs × AWS Environmental Hacks](https://www.wemakedevs.org/aws/env) hackathon — **Air track**.

[![CI](https://github.com/Rohit-998/Environmental-Hacks/actions/workflows/ci.yml/badge.svg)](https://github.com/Rohit-998/Environmental-Hacks/actions/workflows/ci.yml)
&nbsp;·&nbsp; **Live demo:** https://main.d2ji7br4eqzndl.amplifyapp.com
&nbsp;·&nbsp; Region: `ap-south-1`

---

## The problem

On a Delhi winter morning the air can be hazardous before the first bell, and the school running an outdoor PE
period is often the last to know. The official AQI is a 24-hour average that lags the morning; a principal has no
simple, trustworthy way to decide, period by period, *today*, whether to move an activity indoors.

AirDay answers one question for one person: **what should this school change outdoors today, and why.**

## Try the live demo

Open the [demo site](https://main.d2ji7br4eqzndl.amplifyapp.com). It opens on a shared demo school.

- **Today** — the morning plan, period by period, with the hourly PM2.5 chart.
- Pick a **Replay** date (e.g. 19 Nov) from the *Plan from* menu to see a real **Severe** Delhi morning and how the
  plan changes hour by hour.
- **Check an activity** — test any slot up to 2 days ahead against the same rules.
- **Setup** — the school profile and the CSV timetable (demo admin key: `dev`).
- **About** — the full rules table and the data behind every number.

## How it works

```
06:00 IST  →  EventBridge Scheduler  →  Planner Lambda  →  SQS (one job per school)  →  Worker Lambda
                                              │                                              │
                                     warms one forecast                             builds + validates the plan,
                                     per 0.4° grid cell                             stores it, emails the principal
```

The dashboard is a static Next.js site on Amplify. Signed-in principals call `/me/*` with a Cognito JWT that API
Gateway verifies before any Lambda runs; the public demo school is read-only. Full design, failure modes and cost
model are in [docs/architecture.md](docs/architecture.md).

## AWS services used

Everything except the LLM runs on AWS, provisioned as one SAM/CloudFormation stack ([`template.yaml`](template.yaml)).

| Service | How AirDay uses it |
|---|---|
| **AWS Lambda** | Four Python 3.12 functions — `api`, `agent`, `planner` (06:00), `worker` (SQS consumer) — on a shared dependencies layer. x86_64, 512 MB (agent 1024 MB), active tracing. |
| **Amazon API Gateway** (HTTP API) | One HTTP API in front of the Lambdas: per-route throttling, CORS, JSON access logs, and a **Cognito JWT authorizer** on every `/me/*` route. |
| **Amazon Cognito** | User pool + app client. Email sign-in, SRP, 1-hour ID tokens. API Gateway verifies the token; the backend maps its `sub` to the owner's school server-side. |
| **Amazon DynamoDB** | Single-table design (`PK`/`SK`), on-demand billing, point-in-time recovery, TTL, encryption at rest. Every access pattern is a `GetItem` or a single-partition `Query` — no scans. |
| **Amazon SQS** | Fan-out jobs queue + dead-letter queue. One message per school, batch of 10, partial-batch failures (`ReportBatchItemFailures`), 3 receives → DLQ. |
| **Amazon EventBridge Scheduler** | `cron(0 6 * * ? *)` in `Asia/Kolkata` fires the planner at 06:00 IST daily, with a bounded retry policy. |
| **Amazon SES** | Sends the daily plan email. In the SES sandbox it also issues recipient verification links from the Setup page. |
| **AWS Systems Manager Parameter Store** | Every secret (admin key, data.gov.in, OpenAQ, Gemini) stored as a **SecureString** and read at cold start. No secrets in code, git, or plain env vars. |
| **Amazon CloudWatch** | Structured JSON logs, **EMF custom metrics** (`AirDay` namespace), a dashboard, and alarms: DLQ-not-empty, planner errors, and "no briefs built this hour". |
| **AWS X-Ray** | Distributed tracing on all four functions, annotated by route. |
| **Amazon SNS** | Alarm topic with an email subscription for the CloudWatch alarms. |
| **AWS Budgets** | Monthly cost budget with an 80%-of-threshold email alert. |
| **AWS IAM** | Per-function least-privilege policies **plus a permissions boundary on every role**, and a GitHub **OIDC** deploy role — no long-lived AWS keys in CI. |
| **AWS Amplify Hosting** | Builds and hosts the Next.js static export; auto-deploys on every push to `main`. |
| **Amazon Bedrock** | The agent is wired for Bedrock — `bedrock:InvokeModel` IAM, a `ModelProvider=bedrock` deploy switch, and `BedrockRegion` — but **currently runs on Gemini** because Bedrock model invocation is blocked on new AWS accounts (see below). |
| **AWS CloudFormation / SAM** | The entire stack is one declarative `template.yaml`; `sam deploy --resolve-s3` provisions and updates every resource above. |

Also built on **AWS open-source**: [Powertools for AWS Lambda](https://docs.powertools.aws.dev/lambda/python/latest/)
(logs, metrics, tracing) and the [Strands Agents SDK](https://strandsagents.com) (the chat/translation agent).

## Why Gemini, not Bedrock

The chat assistant and the Hindi translation run on **Google Gemini** (`gemini-3.5-flash`) through the Strands Agents
SDK. We use Gemini **only because Amazon Bedrock model invocation is not available on our new AWS account** — every
Bedrock model (including Amazon Nova) returns `ValidationException: Operation not allowed` in `ap-south-1` and
`us-east-1`. New and free-tier accounts are commonly restricted from Bedrock until AWS lifts the limit.

The model is a **deploy parameter**, so switching back is configuration, not code:

```bash
sam deploy --parameter-overrides ModelProvider=bedrock ModelId=global.amazon.nova-2-lite-v1:0
```

The Gemini key lives in SSM Parameter Store as a SecureString, like every other secret. Only the user's question and
the rule engine's tool results (timetable slots and public air-quality numbers) are ever sent to the model — no
names or emails. The daily email, dashboard, replay and "Check an activity" never call a model.

## Tech stack

| Layer | Choices |
|---|---|
| **Backend** | Python 3.12, [`uv`](https://docs.astral.sh/uv/), standard-library HTTP clients. A pure rules engine with no AWS imports, wrapped by thin Lambda handlers. `pytest`, `ruff`. |
| **Frontend** | Next.js 15 (App Router, TypeScript), static export (`output: "export"`), Amplify Auth for Cognito, `lucide-react`. |
| **AI** | Strands Agents SDK with the Google Gemini provider; two read-only tools that wrap the engine, with a grounding check on the output. |
| **Infra / CI-CD** | AWS SAM, GitHub Actions (lint, tests, backtest, build, cfn-lint) and gated deploy via GitHub OIDC; Amplify builds the frontend on push. |
| **Rules as data** | 35 rules (7 air bands × 5 activity scopes) in [`backend/rules/rules.yaml`](backend/rules/rules.yaml); the engine, validator, dashboard and tests all read it. Each rule cites a source in [`SOURCES.md`](backend/rules/SOURCES.md), and a release test blocks on any unread source. |

## Repository layout

```
backend/          Python 3.12 (uv). Rules engine, API, Lambda handlers, agent, tests
  airday/         engine, rules, validator, aqi, service, store, mailer, fanout, agent, api, devserver
  handlers/       Lambda entry points: api.py, agent.py, planner.py (06:00), worker.py (SQS)
  rules/          rules.yaml (single source of truth) + SOURCES.md (what has been read)
  backtest/       scores the engine against measured Delhi station data
  fixtures/       frozen replay days (real forecast + station + bulletin AQI)
frontend/         Next.js dashboard (App Router, static export) for Amplify Hosting
contracts/        brief.schema.json — the backend ↔ frontend contract
template.yaml     SAM: Lambda, HTTP API + Cognito, DynamoDB, SQS, Scheduler, SES, CloudWatch, X-Ray, SNS, Budgets
amplify.yml       Amplify build spec for the frontend
docs/             architecture, decision records (ADRs), deploy guide, IAM policies
```

## Run locally

No AWS account needed — the backend runs on an in-memory store.

Backend:

```bash
cd backend && uv sync && uv run python -m airday.devserver
```

Frontend (in a second terminal):

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000. Pick a replay date from the *Plan from* menu to see a Very Poor morning. The local demo
admin key is `dev`; "Sign in" locally uses a stand-in user, and each name gets its own school.

Settings and secrets live in `backend/.env` (copy `backend/.env.example`; gitignored). Optional data keys:
`DATA_GOV_API_KEY` (official AQI) and `OPENAQ_API_KEY` (station readings). Chat and translation need the agent extra
(`uv sync --extra agent`) and `GEMINI_API_KEY`; `uv run python scripts/chat_smoke.py` tests them.

## Tests

```bash
cd backend && uv run pytest
```

128+ tests cover the engine, validator, tenancy, the fan-out claim protocol, and the API. The **release check** fails
while any emitted rule cites a source nobody has marked as read:

```bash
cd backend && RELEASE=1 uv run pytest
```

## Backtest — does the advice match reality?

```bash
cd backend && uv run python -m backtest.run
```

Scores the engine against 9 Delhi reference stations, Oct–Dec 2025, over school hours on school days. Results in
[`backend/backtest/report.md`](backend/backtest/report.md); CI reruns it and fails if the committed report changes.

| Strategy | Very Poor+ hit rate | False alarms |
|---|---|---|
| 06:00 email, forecast only | 30% | 4% |
| 06:00 email, station band as a floor (production) | **93%** | 12% |
| Live dashboard, forecast + station escalation | 94% | 9% |

CAMS reads ~100 µg/m³ cleaner than Delhi stations in winter, so the forecast alone misses most bad hours. That result
shaped the design: the production brief floors the school day at the latest fresh station band ([ADR 0004](docs/adr/0004-station-floor.md)).

## Deploy

See [docs/deploy.md](docs/deploy.md) for the full walkthrough: SSM secrets, SES setup, `sam deploy`, the GitHub OIDC
deploy role, and Amplify. In short:

```bash
cd backend && bash scripts/build_lambda.sh          # Linux wheels, no Docker
sam deploy --guided                                  # first time; writes frontend env from stack outputs
```

Pushing to `main` then runs CI and, once the `AWS_DEPLOY_ROLE_ARN` variable is set, deploys automatically.

## Data & honesty

- **Forecast:** CAMS Global via [Open-Meteo](https://open-meteo.com) — city-area resolution (~40 km), not street level.
- **Station readings:** OpenAQ / CPCB, used only to *raise* a band, never to lower one.
- **Official AQI:** CPCB via data.gov.in, shown for reference; it never feeds a rule.
- AirDay decides on **hourly PM2.5/PM10 concentrations**, not on the 24-hour AQI, and never calls an hourly number
  "AQI". GRAP stage is indicative, not a CAQM order.
- General guidance based on public health advisories — **not medical advice**.

## More

- [PRD.md](PRD.md) — full product spec and mapping to the judging criteria.
- [docs/architecture.md](docs/architecture.md) — system design, data model, reliability, security, cost, scaling.
- [docs/adr/](docs/adr/) — the key design decisions, one short record each.

Hackathon submission, released under the [MIT License](LICENSE).




