# AirDay

Daily air-safety plans for school timetables. Built for the WeMakeDevs Environmental Hacks (Air track).

AirDay reads the hourly PM2.5/PM10 forecast for the city, checks it against the school's outdoor timetable
(assembly, recess, PE), and emails the principal a plan at 06:00 IST: what changes today, period by period,
with a parent note in English and Hindi. Every recommendation carries a rule ID traced to `backend/rules/rules.yaml`.

See [PRD.md](PRD.md) for the full spec.

## Layout

```
backend/     Python 3.12 (uv). Rules engine, API, Lambda handlers, Strands agent, tests
  airday/    engine, rules, validator, sources, store, service, mailer, api, agent, devserver
  handlers/  Lambda entry points: api.py, agent.py, planner.py (06:00), worker.py (SQS)
  backtest/  scores the engine against measured station data
  rules/     rules.yaml (single source of truth), SOURCES.md (what has been read)
  fixtures/  frozen replay days
frontend/    Next.js (App Router, TypeScript, static export) for Amplify Hosting
contracts/   brief.schema.json, the backend/frontend contract
template.yaml  SAM: DynamoDB, HTTP API + Cognito, SQS fan-out, Scheduler, X-Ray, dashboard, alarms
docs/        architecture, decision records, deploy guide
```

## Run locally

Backend (in-memory store, no AWS needed):

```bash
cd backend && uv sync && uv run python -m airday.devserver
```

Frontend:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000. Pick a replay date from the "View" menu to see a Very Poor morning.
The local demo admin key is `dev`. "Sign in" locally uses a stand-in user; each name gets its own school.

Settings and secrets live in `backend/.env` (copy `backend/.env.example`; gitignored). Optional data keys:
`DATA_GOV_API_KEY` (official AQI) and `OPENAQ_API_KEY` (station readings). Chat and translation need the agent
extra (`uv sync --extra agent`) and `GEMINI_API_KEY`; `uv run python scripts/chat_smoke.py` tests them.

## Why Gemini, not Bedrock

The chat assistant and the Hindi translation run on **Google Gemini** (`gemini-3.5-flash`) through the
[Strands Agents SDK](https://strandsagents.com) (AWS open source). We use Gemini **only because Amazon Bedrock
model invocation is not available on our new AWS account**: every Bedrock model, including Amazon Nova 2 Lite
and Nova Lite, returns `ValidationException: Operation not allowed` for this account in ap-south-1 and us-east-1.
New and free-tier accounts are often restricted from Bedrock until AWS lifts the limit.

Everything else runs on AWS. The model is a deploy parameter, so switching back is configuration, not code:

```bash
sam deploy --parameter-overrides ModelProvider=bedrock ModelId=global.amazon.nova-2-lite-v1:0
```

The Gemini key is stored in SSM Parameter Store as a SecureString, like every other secret. Only the user's
question and the rule engine's tool results (school timetable slots and public air-quality numbers) are sent to
Gemini. No names, emails or other personal data are sent. The daily email, dashboard, replay and "Check an
activity" form never call a model.

## Tests

```bash
cd backend && uv run pytest
```

Release check (fails while any emitted rule cites a source nobody has read yet):

```bash
cd backend && RELEASE=1 uv run pytest
```

## Deploy

See [docs/deploy.md](docs/deploy.md): SSM secrets, SES, `sam deploy`, GitHub OIDC for continuous deploy, and
Amplify Hosting for the dashboard. Architecture, failure modes and decisions are in
[docs/architecture.md](docs/architecture.md).

## Backtest

```bash
cd backend && uv run python -m backtest.run
```

Scores the engine against 9 Delhi stations, Oct–Dec 2025. Results: [backend/backtest/report.md](backend/backtest/report.md).

## Data

Forecast: CAMS Global via Open-Meteo (city-area, ~40 km). Station readings: OpenAQ / CPCB.
Official AQI: CPCB via data.gov.in. General guidance based on public advisories, not medical advice.
