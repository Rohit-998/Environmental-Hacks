# PRD: AirDay: daily air-safety plans for school timetables

Track: Air (Environmental Hacks, Bharat Builds Tour)
Team: multi-person, four roles (§15)
Build window: Thu Oct 8 to Sun Oct 11, 2026. Saturday is polish only (DTU build day).
Status as of Thu 19:15 IST: built and tested locally, not yet deployed (§14).

Deeper detail lives in [docs/architecture.md](docs/architecture.md) (system, failure modes, security, cost),
[docs/adr/](docs/adr/) (decisions) and [backend/backtest/report.md](backend/backtest/report.md) (accuracy).

---

## 1. Problem

From October to January, stubble burning and winter inversions push Delhi NCR air into the "Very Poor" and "Severe" ranges. Children are among the most exposed: they breathe faster for their size and spend part of every school day outdoors for assembly, recess and PE.

Principals already decide every morning whether assembly is held outdoors and whether PE goes ahead. Today they decide by gut feel, a glance at an AQI app, or a government order that may arrive late. A number like "AQI 312" doesn't tell them what to do about Class 6B's PE at 8:40 AM.

The data says the problem is common: in our backtest of 9 Delhi stations, Oct–Dec 2025, 71% of school hours on school days were Very Poor or worse, and on 538 station-days the 08:00–10:00 window, when morning PE usually runs, was Very Poor or worse (§5).

Claims still to confirm with a real principal before the video: how principals decide today, and how often outdoor activities run on Very Poor mornings.

## 2. Solution

AirDay reads the hourly pollution forecast for the city, raises it to the latest station reading where the station is worse, checks it against each school's own timetable, and emails the principal a plan before 7 AM. The decision is in the subject line, and changes are listed first:

> **Subject:** AirDay Fri 9 Oct: 4 changes today. Air in the Very Poor range 08:00–11:00
>
> Official CPCB AQI, Rohini station (24-hr rolling, as of 05:00): 284 Poor · Indicative GRAP stage: I (from Delhi average AQI, not a CAQM order)
>
> **What changes today**
> - Morning assembly (07:50–08:10): hold indoors. [R-VP-ASM]
> - Class 6B PE (08:40–09:20): move indoors for light activity. [R-VP-PE]
> - Recess (10:30–10:50): hold indoors. [R-VP-REC]
> - Windows 08:00–11:00: keep closed. [R-VP-WIN]
>
> **As normal:** Class 8A PE (13:20–14:00) [R-MOD-PE]
>
> Parent note ready in English and Hindi. Copy for WhatsApp on the dashboard.

What changes for Sunita: one email at 06:00 she can act on before the 7:30 bus, a parent note she can paste into the class WhatsApp groups, and a way to check an event ("Can we hold sports day tomorrow afternoon?") against the same rules.

The forecast is a city-area forecast (about 40–45 km per grid cell, §7.6). AirDay never claims to know the air at the school gate. What sets it apart is the timetable: it turns a reading into a period-by-period decision, with a rule ID on every line. The backtest shows a naive "use the 05:00 reading all day" baseline is about as accurate as AirDay's bands, so the value is the decision and its delivery, not a better forecast. The pitch says so.

Any number of schools can sign up. Each principal sees only their own school; a shared demo school is open to everyone, read-only.

## 3. Users

| User | Need | How they get it |
|---|---|---|
| Principal / admin (primary) | Decide quickly what changes today; plan events | Sign in, set up the school, 06:00 email, dashboard, "Check an activity", chat |
| Teachers | Know if their outdoor period moved | The principal forwards the email; one line per activity |
| Parents | Know if their child is safe and what to send | The principal pastes the note into WhatsApp ("Copy for WhatsApp") |
| Judges and visitors | See it working without an account | Public demo school with replay days |

AirDay emails only the principal. It does not contact teachers or parents directly.

Primary persona: Sunita, principal of a 900-student private school in Rohini, Delhi. She checks her phone at 6:45 AM, isn't technical, and has to decide before the 7:30 AM bus arrives.

## 4. Goals and non-goals

Goals
- A principal reads the plan for the day in under 30 seconds (measured, §5).
- Every recommendation is tied to an hour, and to a scheduled activity where there is one, and carries a rule ID traceable to a source.
- The advice is measured against reality, and the measurement is reproducible (backtest in CI).
- The official CPCB AQI is shown next to AirDay's hourly view and never feeds any rule.
- The daily run works for many schools: one forecast fetch per grid cell, one isolated job per school, at most one automatic email per school per day, never a silent failure.
- Each school's data is isolated: a principal can only read or change their own school.

Non-goals (hackathon)
- No sensors or hardware.
- General guidance based on public advisories, not medical advice for individual children. Moving indoors reduces exertion; it does not make indoor air clean.
- No SMS (SNS SMS to India needs DLT registration). Email only; WhatsApp is copy-paste now and an integration later.
- No per-school rule tuning (P2).
- No district or multi-school admin view (P2).
- AirDay doesn't replace GRAP orders or government school closures.

## 5. Success metrics

Accuracy (measured, [backend/backtest/report.md](backend/backtest/report.md)): 9 Delhi reference stations, Oct–Dec 2025, school hours 07:00–13:00 on Mon–Sat, 4,447 hours.

| Strategy | Very Poor+ hit rate | Very Poor+ false alarms | Poor+ hit rate |
|---|---|---|---|
| 06:00 email, forecast only (first design) | 30% | 4% | 52% |
| **06:00 email, latest station band as a floor (production)** | **93%** | **12%** | **95%** |
| 06:00 email, forecast scaled by station/forecast ratio | 86% | 8% | 90% |
| Live dashboard, forecast + station escalation, 1 h lag | 94% | 9% | 96% |
| Baseline: 05:00 station reading all day | 96% | 11% | 96% |

CAMS PM2.5 reads 103 µg/m³ cleaner than the stations on average (MAE 106 µg/m³) during school hours. Target: keep the production row's Very Poor+ hit rate at or above 90%. CI re-runs the backtest on every push and fails if the committed report changes.

Demo
- Sign-up to a saved school and timetable in under 3 minutes (CSV/paste or "Use sample timetable").
- **Outsider test, Saturday at DTU:** 3 people outside the team each read the email and answer "What happens to Class 6B's PE today?" within 30 seconds. Pass: 3 of 3.
- A real scheduled 06:00 run on AWS, shown by the `daily_brief` log line and the CloudWatch dashboard.
- Tested: a redelivered job sends no second email; an SES failure is retried; one school's failure doesn't block others; a user can't read another school.
- Every brief action has a rule ID that exists in `rules.yaml`, enforced at runtime (an invalid brief is not emailed) and in tests.
- Every chat answer that evaluates an activity cites at least one rule ID returned by a tool in that turn.

Pilot (after the hackathon): brief open rate, parent notes copied, outdoor minutes moved out of Very Poor or worse hours, and a live re-run of the backtest on the pilot schools' own stations.

## 6. Features

Status key: ✅ built and tested locally · ⏳ needs deploy or a person.

### Must (never cut)
1. ✅ **Accounts and schools.** Email sign-up and sign-in with Cognito. A signed-in user creates one school; the school ID comes from the token server-side, never from the client. A public demo school stays readable by everyone; writes to it need the demo admin key while `DemoAdmin=true`.
2. ✅ **School profile.** Name, locality search (Open-Meteo geocoding finds place names, not street addresses) plus editable lat/lon, school hours, school days (default Mon–Sat), holidays, principal email, CPCB station, OpenAQ sensors. Public profile responses never include the email.
3. ✅ **Timetable.** CSV/paste import (`day,start,end,type,label`), "Use sample timetable", and an editable table. Validation: `day` ∈ Mon–Sun (full names accepted), `type` ∈ assembly/recess/pe (synonyms like sports, break accepted), `HH:MM` 24-hour or 12-hour with am/pm, `start < end`, within school hours, at most 200 rows, BOM, header row and Excel tab-paste tolerated. Invalid rows are shown with line and reason, and nothing is saved.
4. ✅ **Forecast ingest.** Hourly PM2.5 and PM10 from the Open-Meteo Air Quality API (CAMS Global), `timezone=Asia/Kolkata`, explicit dates, fetched once per 0.4° grid cell into a shared cache.
5. ✅ / ⏳ **Station readings.** Hourly-average PM2.5 and PM10 from OpenAQ v3 for the school's sensors. Feeds the station floor (§7.6) and the dashboard overlay. ⏳ Sensor IDs for the demo school and the OpenAQ API key.
6. ✅ / ⏳ **Official AQI headline.** data.gov.in CPCB real-time feed, highest sub-index under CPCB's 3-pollutant rule, labelled "24-hour rolling, as of HH:MM". Display only. ⏳ Field meaning of `avg_value` to confirm with a live call.
7. ✅ **Indicative GRAP stage.** From the Delhi average AQI: I 201–300, II 301–400, III 401–450, IV >450. Always labelled "Indicative (from Delhi average AQI, not a CAQM order)". An admin can set the official stage; the override expires after 3 days.
8. ✅ **Rules engine.** Pure function of (timetable, hourly data, station readings, date, now) → actions. Activity-bound (assembly, recess, PE) and hour-bound (windows, parent note). All rule data in `rules.yaml` (§7.5).
9. ✅ **Validator at runtime.** Every action has rule IDs that exist; every timetable activity of the day has exactly one action; no hourly number is labelled "AQI". A brief that fails is not emailed; the principal gets "today's plan could not be built" and the job fails visibly.
10. ✅ / ⏳ **Daily run, many schools.** EventBridge Scheduler at 06:00 IST → planner → SQS → workers (§9). Workers skip non-school days and holidays, and skip runs after 07:30 so a stale plan never arrives mid-morning. ⏳ First real run on AWS.
11. ✅ **Historical replay.** Pick a past date from a fixed list; the pipeline runs "as of 06:00" from frozen fixtures, per school. Stored as `REPLAY#<date>`, never touches real briefs or the email lock. A REPLAY-labelled email can be sent for the video. Fixtures: 19 and 27 Nov 2025.
12. ✅ / ⏳ **Parent note, English and Hindi, from templates.** Per-rule templates in `rules.yaml`. "Copy for WhatsApp" copies plain text. ⏳ Fluent Hindi speaker review.
13. ✅ **Dashboard: Today.** Decision headline, "What changes today" first, "As normal" collapsed, official AQI and GRAP badge with labels, hourly PM2.5 strip with station overlay and a text table, parent note with English/Hindi toggle and copy button, replay picker, a prompt to add a timetable when it's empty.
14. ✅ **Observability.** Powertools for AWS Lambda: structured JSON logs, X-Ray traces, EMF metrics, CloudWatch dashboard, alarms (§9.4).
15. ✅ **Backtest.** `uv run python -m backtest.run` scores the engine against committed station and forecast data and writes the report. Re-run in CI.

### Should (cut in this order if behind)
16. ✅ / ⏳ **Principal chat** (Strands agent). Tools: `get_day(date)` and `evaluate_activity(type, date, start, end)`. Behaviour in §8.2. ⏳ Bedrock access check and a run against the real model.
17. ✅ / ⏳ **Free-text addition, translated.** The principal types one line to append to the parent note; the agent translates it; the validator in §8.3 checks it. ⏳ Real model run.
18. ✅ **"Check an activity" form.** Deterministic `GET /evaluate`, shared with the chat tool. If chat is cut, this keeps the event-planning demo.

Cut order: chat → free-text translation. Everything in Must is never cut. If every LLM job is cut, Strands is no longer used, and AWS eligibility rests on the deployed services, SAM CLI and Powertools.

### P1
- 3-day outlook strip.
- An "outdoor minutes moved" counter across real and replayed days.
- A 07:15 update email if the live plan has changed since 06:00.

### P2
- WhatsApp integration, district view, per-school strictness, indoor sensors, automated GRAP tracking, SES production access and a custom domain.

## 7. Rules

### 7.1 Two quantities, never mixed

| Quantity | Source | Used for |
|---|---|---|
| Hourly PM2.5/PM10 (µg/m³) | Open-Meteo forecast; OpenAQ station hourly averages | All timetable decisions and the station floor |
| Official AQI (24-hr basis) | data.gov.in (live); CPCB bulletin fixture (replay) | Headline and indicative GRAP only |

CPCB defines its breakpoints on 24-hour averages. Applying them to hourly values is AirDay's own cautious choice, not CPCB's method, and the "About the data" page says so. An hourly number is never labelled "AQI". When the two seem to disagree the brief explains it: "Daily average is Poor; this morning's peak is in the Very Poor range." See ADR 0003.

### 7.2 Concentration bands (CPCB breakpoints as half-open intervals, µg/m³)

| Band | PM2.5 | PM10 |
|---|---|---|
| Good | [0, 30] | [0, 50] |
| Satisfactory | (30, 60] | (50, 100] |
| Moderate | (60, 90] | (100, 250] |
| Poor | (90, 120] | (250, 350] |
| Very Poor | (120, 250] | (350, 430] |
| Severe | > 250 | > 430 |

An hour's band is the worse of the two. A value that is null, negative or above 1000 is treated as missing. If one pollutant is missing the other decides; if both are missing the band is `unknown`.

### 7.3 Time handling
- Everything is in IST (Asia/Kolkata). OpenAQ returns UTC and is converted on ingest; an hourly average is assigned to the hour it starts in.
- Hour `h` covers `[h:00, h+1:00)`. An activity uses every hour it overlaps: 08:40–09:20 uses hours 08 and 09; 08:00–09:00 uses hour 08 only.
- Activity band: the worst known band across its hours. If any hour is `unknown` and the worst known band is below Very Poor, the activity is `unknown`. If the worst known band is Very Poor or Severe, that band applies (fail safe).
- CAMS Global is natively 3-hourly and interpolated to hourly by Open-Meteo, so hourly timing is approximate. The UI says "around".

### 7.4 Actions

Principle: the harder the activity, the earlier it is restricted (PE, then recess, then assembly). This is a design principle until a source on exertion during pollution episodes has been read and recorded.

Activity-bound (`kind: activity`):

| Band | Assembly | Recess | PE |
|---|---|---|---|
| Good | Outdoors `R-G-ASM` | Outdoors `R-G-REC` | Normal `R-G-PE` |
| Satisfactory | Outdoors `R-S-ASM` | Outdoors `R-S-REC` | Normal `R-S-PE` |
| Moderate | Outdoors `R-MOD-ASM` | Outdoors `R-MOD-REC` | Normal; students with asthma may sit out `R-MOD-PE` |
| Poor | Outdoors, under 10 min `R-P-ASM` | Outdoors, shortened, no running games `R-P-REC` | Indoors, light activity `R-P-PE` |
| Very Poor | Indoors `R-VP-ASM` | Indoors `R-VP-REC` | Indoors, light activity `R-VP-PE` |
| Severe | Indoors `R-SV-ASM` | Indoors `R-SV-REC` | Cancel; classroom lesson `R-SV-PE` |
| Unknown | Check official AQI first `R-UNK-ASM` | `R-UNK-REC` | `R-UNK-PE` |

Hour-bound (`kind: window` / `note`):

| Band | Windows | Parent note |
|---|---|---|
| Good / Satisfactory / Moderate | Open `R-G-WIN` `R-S-WIN` `R-MOD-WIN` | Not sent `R-G-NOTE` `R-S-NOTE` `R-MOD-NOTE` (`emit: false`) |
| Poor | Closed `R-P-WIN` | Drafted, marked optional: the principal decides whether to send `R-P-NOTE` |
| Very Poor | Closed `R-VP-WIN` | Recommended: mask, water, tell the school about symptoms `R-VP-NOTE` |
| Severe | Closed `R-SV-WIN` | Recommended, plus "watch for school notices; government orders may change timings" `R-SV-NOTE` |
| Unknown | Closed until data returns `R-UNK-WIN` | Not sent `R-UNK-NOTE` (`emit: false`) |

- Window lines merge contiguous school hours with the same instruction (open/closed) and list every rule ID behind them.
- The parent note uses the worst known band in school hours and appears once. An all-unknown day sends no note.
- Every rule has `change: true|false`; the brief lists `change: true` actions under "What changes today".
- The Severe note does not name specific GRAP school measures; those changed in late 2024 and must be quoted from the current schedule if used at all.

### 7.5 One source of truth
`backend/rules/rules.yaml` holds the band thresholds and all 35 rules (7 bands × 5 scopes): ID, band, scope, `change`, `emit`, English template, Hindi template (required where `emit` is true for notes), `basis` (`direct` = quotes a source, `derived` = AirDay's interpretation) and `source` key. The engine, validator, dashboard "About the rules" page and tests all read it. Tests fail on a missing (band × scope) cell or a duplicate ID.

`backend/rules/SOURCES.md` lists each source key with `status` (`pending`/`read`), `read_by` and `read_on`. A release test (`RELEASE=1 pytest`) fails while any emitted rule cites a pending source; CI runs it as a warning until Fri 18:00, then it should become blocking. A rule whose source isn't read by then is reworded as plain guidance with `basis: derived`.

Sources to read (none cited until read): CPCB National AQI (2014) health statements; CAQM GRAP schedule (current revision); WHO or US EPA guidance on reducing exertion during high-pollution episodes. The CPCB "Moderate" statement wording must be checked; it may not mention children and older adults.

### 7.6 Data limits and the station floor
- Open-Meteo air quality uses CAMS Global at 0.4° (about 45 km), 3-hourly. Delhi NCR is one or two grid cells: "city-area forecast". Past data is archived CAMS forecasts from the same endpoint, from August 2022.
- CAMS reads far cleaner than Delhi stations in winter (§5). So when a brief is built, the latest station reading no older than `STATION_MAX_AGE_MIN` (default 120) sets a floor for the rest of the school day (`STATION_FLOOR_HOURS`, default 24). The floor only raises a band, never lowers one, and also fills `unknown` hours. Hours raised this way are marked "escalated: station reading". See ADR 0004.
- The trade-off is deliberate: the floor misses far fewer bad hours (93% caught vs 30%) at the cost of more unneeded indoor periods (12% false alarms vs 4%). Missing a Very Poor hour sends children out to run in it; an unneeded indoor period costs a lesson plan.
- The email is a snapshot "as of 06:00". The dashboard recomputes on load (upstream cached 10 minutes) and shows "Changed since this morning's email" when a band has moved, which covers days that clear up.
- The station lag is assumed to be 1 hour in the backtest until it is measured on live data.
- Data attribution (CAMS/Open-Meteo, OpenAQ, data.gov.in/CPCB) appears in the email footer and the dashboard.

### 7.7 Replay fixtures
`backend/fixtures/replay/<date>.json` holds the frozen Open-Meteo response, OpenAQ hourly readings if available, and the CPCB bulletin city AQI. The bulletin is published around 4 PM, so the replay shows the previous day's city value (what was known at 06:00). Current fixtures: 19 Nov 2025 (Wed, PM2.5 around 187 µg/m³ at 08:00) and 27 Nov 2025 (Thu, backup). ⏳ The bulletin city AQI for both dates is blank and must be read from the bulletin by a person, not entered from memory.

## 8. Agent

### 8.1 Provider
Strands Agents SDK 1.58.1 (AWS open source), provider set by `ModelProvider`/`ModelId`. Default: Amazon Nova Lite through the APAC cross-region inference profile (`apac.amazon.nova-lite-v1:0`), because it needs no Marketplace subscription. Bedrock has no free tier for models; usage draws on the account's credits and costs a fraction of a cent per turn. ⏳ Bake-off: 5 Hindi translations and 5 tool-calling prompts; pass bar 4 of 5 on each; next step Nova Pro. Fallback: Strands' LiteLLM provider. The video names whichever provider is used. See ADR 0005.

### 8.2 Chat
- Context date: the dashboard's selected date (live or replay). "Today" and "tomorrow" are relative to it. Planning window: context date plus 2 days; outside that gets a fixed reply.
- Events (sports day, excursion) are evaluated as PE.
- Output is structured JSON `{answer, ruleIds}`. If `evaluate_activity` was called, `ruleIds` must be non-empty, and every ID must have come from a tool in that turn. One retry, then the raw tool result is shown.
- Tools are scoped to the caller's school and read-only.
- At most 4 tool calls; Lambda timeout 25 s (HTTP API limit is 30 s). Input capped at 500 characters; last 6 messages sent by the client; nothing stored.
- Daily cap per school: 200 agent calls (`COUNTER#<date>` / `AGENT#<school>`).
- Medical questions get a fixed reply pointing to a doctor and never reach the model.

### 8.3 Translation check
Normalise Devanagari digits (०–९) to ASCII; every number and `HH:MM` time in the English must appear in the Hindi; at least 60% of letters must be Devanagari; length 0.5×–2.5× of the English; at most 300 characters. On failure the addition stays English-only with a visible note.

## 9. Architecture

Full version with failure modes, security, cost and scaling limits: [docs/architecture.md](docs/architecture.md).

```
EventBridge Scheduler (06:00 IST)
   └─► Planner Lambda ── warms 1 forecast per 0.4° grid cell ──► Open-Meteo
          └─► SQS jobs (1 message per school) ──► Worker Lambda (batch 10, partial failures)
                 │        └─ 3 failed receives ─► DLQ ─► alarm
                 ├─► OpenAQ · data.gov.in
                 ├─► DynamoDB (brief, email claim)
                 └─► SES → principal

Principal ─► Next.js static site (Amplify Hosting) ─► Cognito (sign-in)
          └─► API Gateway HTTP API (JWT authorizer on /me/*)
                 ├─► API Lambda    (school, timetable, brief, replay, evaluate)
                 └─► Agent Lambda  (chat, translate; Strands → Bedrock Nova Lite)

All Lambdas ─► DynamoDB single table · CloudWatch (JSON logs, EMF metrics) · X-Ray
```

AWS services: Lambda, EventBridge Scheduler, SQS, DynamoDB, SES, API Gateway HTTP API, Cognito, Amplify Hosting, Bedrock, CloudWatch, X-Ray, SNS (alarms), SSM Parameter Store, AWS Budgets. AWS open source: Strands Agents SDK, Powertools for AWS Lambda, SAM CLI.

### 9.1 Stack and repo layout
- Backend: Python 3.12, `uv`, `pytest`, `ruff`. One package `airday` shared by all Lambdas; the engine has no AWS imports. A local dev server (`uv run python -m airday.devserver`) serves the same API from an in-memory store, with a stand-in sign-in (`x-dev-user`) that the deployed API never honours.
- Frontend: Next.js 15.5.27 (App Router, TypeScript), static export, Amplify Auth for Cognito.
- Infrastructure: one SAM template, linted with cfn-lint.

```
/backend
  /airday        engine, rules, aqi, validator, sources, store, service, fanout, mailer, auth, api, agent, obs, devserver
  /handlers      api.py, agent.py, planner.py, worker.py
  /rules         rules.yaml, SOURCES.md
  /fixtures      replay/<date>.json
  /backtest      fetch.py, run.py, data/, report.md
  /tests
/contracts       brief.schema.json (additive changes only)
/frontend        Next.js app
/docs            architecture.md, adr/, deploy.md
/.github         workflows/ci.yml
template.yaml, amplify.yml
```

### 9.2 Daily fan-out
- The planner reads the school registry, snaps each school to its grid cell, fetches each cell's forecast once into the shared `CACHE` partition, and sends one SQS message per school. Delhi with 1,000 schools is two or three forecast calls. See ADR 0006.
- Workers process batches of 10 and report only failed messages back (`ReportBatchItemFailures`). After 3 receives a message moves to the DLQ, which alarms.
- Worker reserved concurrency 20 caps load on SES and upstream APIs. Queue visibility 6 minutes, retention 2 hours (an older brief is useless). Scheduler retries the planner twice within 30 minutes.

### 9.3 Email send protocol
`SCHOOL#<id>` / `EMAIL#<date>` with `status` ∈ SENDING/SENT/FAILED and `attempts`.
1. Claim with a conditional update: item absent, or `status = FAILED` and `attempts < 3`. If the claim fails, stop (already sent or in progress).
2. Send through SES. On success set SENT; on error set FAILED and raise, so SQS redelivers the job.
3. The remaining edge case: a crash after SES accepted the message but before SENT is recorded produces no second email. The guarantee is "at most one automatic email per school per day, retried on known failure".

Manual regenerate rebuilds the brief and only emails with `resend=true`. Replays never take the lock.

### 9.4 Observability
- Powertools for AWS Lambda on every function: JSON logs with Lambda context, X-Ray tracing, EMF metrics in the `AirDay` namespace (`SchoolsQueued`, `BriefBuilt`, `BriefFailed`, `BriefSkipped`, `EmailSent`, `ChangesRecommended`, `StationEscalations`, `ForecastCellsWarmed`, `Http2xx/4xx/5xx`).
- One `daily_brief` log line per school per day: bands, rule IDs, escalated hours, upstream status, email result. This is the evidence in the video.
- CloudWatch dashboard `airday-<stage>`; alarms for DLQ not empty, planner errors and "no briefs built this hour"; AWS Budgets alert at 80% of $5.
- API Gateway access logs with route, status, latency and the caller's `sub`.

### 9.5 Upstream failures
Every call has a 5 s timeout and one retry. Open-Meteo down: stale cache marked "cached from HH:MM"; none cached: every activity becomes `R-UNK-*` and the headline says "Forecast unavailable today". OpenAQ or data.gov.in down: the field shows "unavailable" and the brief still goes out.

## 10. API

Two route trees share the same handlers: `/…` serves the public demo school; `/me/…` serves the signed-in user's own school, behind the Cognito JWT authorizer.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/me` | Cognito | Who am I, which school, can I write |
| POST | `/me/school` | Cognito | Create my school (one per user) |
| GET / PUT | `/school`, `/me/school` | read: public · write: demo key / Cognito | Profile without email; update, GRAP override |
| GET / PUT | `/activities`, `/me/activities` | same | Timetable; replace (CSV or JSON) with per-row errors |
| GET | `/activities/sample` | public | Sample timetable CSV |
| GET | `/brief?date=`, `/me/brief` | same | Stored live brief |
| GET | `/brief/live`, `/me/brief/live` | same | Recomputed now, with diff against the stored brief |
| POST | `/brief/regenerate?date=&resend=` (+ `/me`) | write | Rebuild; email only if `resend=true` |
| GET | `/replay/dates` | public | Available replay dates |
| GET | `/replay?date=` (+ `/me`) | read | Replay brief for that school |
| POST | `/replay/email?date=` (+ `/me`) | write | Send a REPLAY-labelled email |
| GET | `/evaluate?type=&date=&start=&end=&mode=` (+ `/me`) | read | Deterministic activity check |
| POST | `/chat`, `/me/chat` | read, capped | Chat (agent Lambda) |
| POST | `/note/translate`, `/me/note/translate` | write, capped | Free-text translation (agent Lambda) |
| GET | `/rules`, `/health` | public | Rules table; health |

- The school ID is resolved from the token's `sub` via `USER#<sub>`; a `schoolId` sent by the client is ignored.
- Demo admin key: random 32-byte value in SSM SecureString, constant-time compare, only honoured while `DemoAdmin=true`. Turn it off after the video.
- Throttling: 25 rps (burst 50) default; `/chat` and `/note/translate` 1 rps (burst 3); `/me/chat` 2 rps (burst 5). Plus the per-school agent cap and the budget alert.
- CORS allows the Amplify domain and `localhost:3000`; CORS is not protection, the authorizer, keys and caps are.

## 11. Accessibility and design
- Band colours always carry the band name as text; the hourly strip has a text-table alternative.
- WCAG 2.1 AA contrast (4.5:1 body text); keyboard-reachable controls with visible focus; labelled fields; skip link.
- Email reads correctly with images off and has a plain-text part.
- Hindi text has `lang="hi"`. Times are 24-hour `HH:MM`. Plain words, no jargon.
- Works at 360 px wide.

Full WCAG validation needs manual testing with assistive technology; these rules are the baseline, not a compliance claim.

## 12. Data model (DynamoDB single table)

On-demand, point-in-time recovery, encryption at rest, `DeletionPolicy: Retain`, TTL on `expiresAt`. See ADR 0002.

| PK | SK | Holds |
|---|---|---|
| `SCHOOL#<id>` | `PROFILE` | name, locality, lat, lon, start, end, schoolDays[], holidays[], principalEmail, cpcbStation, openaqSensors, grapOverride, owner |
| `SCHOOL#<id>` | `ACTIVITY#<id>` | day, start, end, type, label |
| `SCHOOL#<id>` | `BRIEF#<date>` | brief JSON (schemaVersion, rulesVersion, mode=live, schoolId) |
| `SCHOOL#<id>` | `REPLAY#<date>` | brief JSON (mode=replay) |
| `SCHOOL#<id>` | `EMAIL#<date>` | status, attempts, updatedAt, messageId |
| `USER#<sub>` | `SCHOOL` | schoolId owned by this Cognito user |
| `REGISTRY` | `SCHOOL#<id>` | schoolId, grid cell, name (read by the planner) |
| `CACHE` | `openmeteo#<cell>#<date>`, `openaq#<sensor>#<date>`, `datagov#Delhi#latest` | raw response, fetchedAt (TTL 2 days) |
| `COUNTER#<date>` | `AGENT#<school>` | n (TTL 7 days) |

`contracts/brief.schema.json` is the contract between backend and frontend; API responses validate against it in tests.

## 13. Testing and CI

99 backend tests pass locally (1 release check skipped by design). `ruff`, `eslint`, `next build` and `cfn-lint` are clean.

| Area | Tests |
|---|---|
| Bands | Boundaries 30 / 30.01 / 90.4 / 250 / 250.01 and PM10 equivalents; null, negative and >1000 values; both missing → unknown |
| Time | Two-hour overlap takes the worse band; ending on the hour doesn't touch the next; unknown + Very Poor stays Very Poor; unknown + Moderate is unknown; UTC→IST |
| Rules file | 35 cells, no duplicates, emitted notes have Hindi, source keys exist; release test for read sources |
| Escalation | Raises only; fills unknown; ignored when stale; station freshness |
| Brief | One action per activity; window runs merged by instruction; one parent note; changes first; subject line |
| Email | Duplicate invocation → one send; SES failure → FAILED then retry → SENT; attempts cap |
| Tenancy | `/me` needs a user; users see only their own school; client-supplied school ID ignored; one school per user; demo is read-only; demo writes can be disabled |
| Fan-out | One forecast fetch per grid cell; workers use the shared cache; SQS redelivery sends one email; partial batch failures; non-school days and late runs skipped |
| Handlers | API Gateway event with and without JWT claims; worker partial batch response; planner enqueues one job per school |
| Validator | Rejects unknown or missing rule IDs, a missing activity, "AQI" next to an hourly number |
| Official AQI | Max sub-index; fewer than 3 pollutants → unavailable; GRAP thresholds; override expiry |
| Translation | Devanagari digits accepted; missing number or time rejected; Latin-only output rejected |
| Chat grounding | Uncited evaluation rejected then raw rules shown; out-of-range date gets fixed reply; medical questions never reach the model; tool-call cap; per-school daily cap |
| Contract | Briefs validate against the schema |
| Backtest | CI re-runs it and fails if `report.json` changes |

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request: backend lint and tests, backtest reproducibility, release check (warning only for now), frontend lint and build, cfn-lint, and a check that `requirements.txt` matches `uv.lock`. A deploy job (SAM, GitHub OIDC, no stored keys) runs on `main` only once the `AWS_DEPLOY_ROLE_ARN` repository variable is set. ⏳ The first CI result hasn't been checked; see the Actions tab.

## 14. Build status (Thu 19:15 IST)

Done and pushed: everything marked ✅ in §6, the SAM template, CI, the backtest, and the docs.

Remaining, by owner:

| Owner | Task | By |
|---|---|---|
| Everyone | Verify as a student on AWS Builder Center; read the Rules page for the deadline time and submission format | Thu night |
| Data & infra | Check the first CI run is green | Thu night |
| Data & infra | Create SSM secrets, verify the SES sender and principal addresses, confirm Nova Lite works via the APAC profile | Fri 10:00 |
| Data & infra | First `sam deploy`, Amplify Hosting with the Cognito variables, set `DashboardUrl` and `CorsOrigins`; then add the GitHub OIDC role so CI deploys | Fri 13:00 |
| Data & infra | Find OpenAQ sensor IDs for the demo school, measure live station lag, confirm the data.gov.in `avg_value` meaning | Fri 15:00 |
| Rules & content | Read the three sources and mark them in `SOURCES.md`, or reword rules as derived guidance; make the release check blocking | Fri 18:00 |
| Rules & content | Fluent Hindi review of every note template; fill the bulletin city AQI for both replay dates from the bulletin | Fri 18:00 |
| Backend | Run chat and translation against the real model; tune prompts if the bake-off fails | Fri 18:00 |
| Frontend | Outsider test script and copy polish | Fri 20:00 |
| Everyone | Feature freeze | Fri 22:00 |

The team chose to deploy once the build is done, so the first real 06:00 run will be **Sat 06:00** (Sat is a school day; Sunday is skipped). That is the only real run before the video. If the deploy can happen on Thursday night instead, Friday 06:00 becomes a second chance.

## 15. Timeline (remaining)

Roles: **Backend** (engine, API, email, agent), **Data & infra** (sources, SAM, AWS, CI), **Frontend** (Next.js), **Rules & content** (rules, sources, Hindi, replay dates, video, blog).

| When | Milestone |
|---|---|
| Thu night | Student verification, Rules page, CI green |
| Fri 13:00 | Deployed: API, Cognito, Amplify dashboard, schedule live; demo school reachable at the public URL |
| Fri 18:00 | Sources read or rules reworded; Hindi reviewed; bulletin values filled; chat checked on the real model |
| Fri 22:00 | Feature freeze |
| Sat 06:00 | First real scheduled run; capture the CloudWatch dashboard and the `daily_brief` log line |
| Sat (DTU) | Polish only. Outsider test. 10-second clip with consent. Rough cut of the video in the evening |
| Sun | Final video (aim 2:50), Builder Center blog, set `DemoAdmin=false`, submit by an internal 18:00 deadline |

## 16. Demo video (3 minutes)

| Time | Shows | Criterion |
|---|---|---|
| 0:00–0:20 | Teacher or parent clip (with consent), smoggy assembly (own or licensed footage), "71% of school hours last winter were Very Poor or worse" | Impact |
| 0:20–0:40 | Sunita signs up, finds her locality, pastes the timetable; one invalid row is rejected | Usability |
| 0:40–1:35 | Replay of 19 Nov 2025: the REPLAY email arrives with the decision in the subject; dashboard with official AQI and GRAP labels, hourly strip with station overlay and an escalated hour, "Class 6B PE: indoors [R-VP-PE]", Hindi note copied to WhatsApp | Impact, usability, execution |
| 1:35–1:55 | "Can we hold sports day tomorrow afternoon?" The answer cites a rule | Execution |
| 1:55–2:15 | Backtest: forecast alone caught 30% of Very Poor hours; with the station floor, 93%. "We measured it, and changed the design" | Execution, impact |
| 2:15–2:40 | Architecture diagram: Scheduler → planner → SQS → workers, one forecast per city; Cognito; CloudWatch dashboard and the real Sat 06:00 log line | Built on AWS |
| 2:40–2:50 | Tests and CI green, "every action traces to a cited rule", what's next | Execution |

Rule IDs stay visible in every frame that shows a brief.

## 17. Risks

| Risk | Mitigation |
|---|---|
| Deploy slips past Friday, so no real run before the video | Deploy target Fri 13:00; docs/deploy.md is step by step; Sat 06:00 is the fallback, a manual planner invoke is the last resort (labelled as such) |
| CAMS under-predicts or Open-Meteo is down | Station floor; stale cache; `R-UNK-*` with "check the official AQI" |
| Station floor too strict on days that clear | Live dashboard recomputes and flags changes; 12% false-alarm rate is stated openly |
| OpenAQ lag longer than assumed | Measure Friday; `STATION_MAX_AGE_MIN` is a parameter; re-run the backtest with the measured lag |
| data.gov.in fields mean something else | Friday check; station AQI shown only when computable |
| Cognito or JWT authorizer misconfigured | Tenancy logic is tested locally; smoke-test `/me` right after deploy; the demo school works without sign-in |
| Provider unavailable or weak Hindi | Bake-off; notes are templates and unaffected; chat is cuttable |
| Chat gives ungrounded advice | Structured output, rule-ID check, retry, raw tool result |
| SES sandbox or spam folder | Verify recipients Friday; test inboxes; request production access only if needed |
| Sources not read in time | Fri 18:00 deadline; reword as derived guidance |
| Public endpoints drain credits | Per-school daily cap, route throttling, budget alert, `DemoAdmin=false` after the video |
| Student verification missed | Thursday task for everyone |

## 18. Open questions
- Product name (AirDay is a placeholder).
- Who attends DTU on Saturday. The plan holds either way.
- Whether to deploy tonight for a Friday 06:00 run, or stay with the Friday 13:00 plan.

## 19. Changes from previous version
- **Many schools.** Sign-in with Cognito, one school per user, server-side tenant resolution, public read-only demo school. "No login" and "multiple schools (P2)" are gone.
- **Fan-out.** The single 06:00 Lambda became planner → SQS → workers with a DLQ, partial batch failures, reserved concurrency and one forecast fetch per CAMS grid cell.
- **Accuracy measured.** New backtest against 9 Delhi stations, Oct–Dec 2025, reproduced in CI. It showed the forecast alone caught 30% of Very Poor hours.
- **Escalation changed because of it.** The 3-hour station escalation became a station floor for the rest of the school day (93% caught, 12% false alarms). Problem statement and pitch now cite the measured numbers, including that a naive baseline is about as accurate.
- **Observability.** Powertools for AWS Lambda (logs, X-Ray, EMF metrics), a CloudWatch dashboard, three alarms and a budget alert.
- **CI/CD.** GitHub Actions for lint, tests, backtest, frontend build and cfn-lint; deploy via GitHub OIDC once the role exists.
- **Docs.** Architecture doc, six decision records, deploy guide.
- **API** split into `/…` (demo) and `/me/…` (signed-in) trees; per-school agent cap; demo writes can be switched off.
- **Data model** adds `USER#`, `REGISTRY` and a shared `CACHE` partition; tenant data is under `SCHOOL#<id>`.
- **Timeline** rewritten as build status and remaining tasks; first real run moves to Sat 06:00 because deploy happens after the build.
- **Video** adds the backtest segment and the fan-out story.
