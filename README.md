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
  handlers/  Lambda entry points: api.py, brief.py (06:00 schedule), agent.py (chat/translate)
  rules/     rules.yaml (single source of truth), SOURCES.md (what has been read)
  fixtures/  frozen replay days
frontend/    Next.js (App Router, TypeScript, static export) for Amplify Hosting
contracts/   brief.schema.json, the backend/frontend contract
template.yaml  SAM: DynamoDB, HTTP API, 3 Lambdas, EventBridge Scheduler, alarm
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
The local admin key is `dev` (enter it on the Setup page).

Optional local data keys: `DATA_GOV_API_KEY` (official AQI) and `OPENAQ_API_KEY` (station readings).
Chat and translation need the agent extra (`uv sync --extra agent`) plus AWS credentials with Bedrock access.

## Tests

```bash
cd backend && uv run pytest
```

Release check (fails while any emitted rule cites a source nobody has read yet):

```bash
cd backend && RELEASE=1 uv run pytest
```

## Deploy

1. Create the secrets (once):

   ```bash
   aws ssm put-parameter --name /airday/admin-key --type SecureString --value "$(openssl rand -hex 32)"
   ```

   Optionally `/airday/data-gov-key` and `/airday/openaq-key` the same way.
2. Verify the SES sender and the principal's address (SES sandbox).
3. Build and deploy the backend:

   ```bash
   sam build && sam deploy --guided
   ```

4. Connect the repo in Amplify Hosting (it reads `amplify.yml`), and set `NEXT_PUBLIC_API_URL` to the `ApiUrl` output.
   Then add the Amplify domain to the `CorsOrigins` parameter and redeploy.

## Data

Forecast: CAMS Global via Open-Meteo (city-area, ~40 km). Station readings: OpenAQ / CPCB.
Official AQI: CPCB via data.gov.in. General guidance based on public advisories, not medical advice.
