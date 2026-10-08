# PRD: AirDay: daily air-safety plans for school timetables

Track: Air (Environmental Hacks, Bharat Builds Tour)
Team: multi-person, four roles (§14)
Build window: Thu Oct 8 (from 14:00 IST) to Sun Oct 11, 2026. Saturday is polish only (DTU build day).

---

## 1. Problem

From October to January, stubble burning and winter inversions push Delhi NCR air into the "Very Poor" and "Severe" ranges. Children are among the most exposed: they breathe faster for their size and spend part of every school day outdoors for assembly, recess and PE.

Principals already decide every morning whether assembly is held outdoors and whether PE goes ahead. Today they decide by gut feel, a glance at an AQI app, or a government order that may arrive late. A number like "AQI 312" doesn't tell them what to do about Class 6B's PE at 8:40 AM.

Claims to source or confirm with a real principal before the video: how principals decide today, and how often outdoor activities run on Very Poor mornings.

## 2. Solution

AirDay reads the hourly pollution forecast for the city, checks it against the school's own timetable, and emails the principal a plan before 7 AM. The decision is in the subject line, and changes are listed first:

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

What changes for Sunita: she gets one email at 06:00 that she can act on before the 7:30 bus, a parent note she can paste into the class WhatsApp groups, and a way to check an event ("Can we hold sports day tomorrow afternoon?") against the same rules.

The forecast is a city-area forecast (about 40–45 km per grid cell, §7.6). AirDay never claims to know the air at the school gate. What sets it apart is the timetable: it matches hourly forecasts to the activities scheduled in those hours.

## 3. Users

| User | Need | How they get it |
|---|---|---|
| Principal / admin (primary) | Decide quickly what changes today; plan events | 06:00 email, dashboard, "Check an activity" form, chat |
| Teachers | Know if their outdoor period moved | The principal forwards the email; one line per activity |
| Parents | Know if their child is safe and what to send | The principal pastes the note into WhatsApp ("Copy for WhatsApp") |

AirDay emails only the principal. It does not contact teachers or parents directly.

Primary persona: Sunita, principal of a 900-student private school in Rohini, Delhi. She checks her phone at 6:45 AM, isn't technical, and has to decide before the 7:30 AM bus arrives.

## 4. Goals and non-goals

Goals
- A principal reads the plan for the day in under 30 seconds (measured, §5).
- Every recommendation is tied to an hour, and to a scheduled activity where there is one, and carries a rule ID traceable to a source.
- The official CPCB AQI is shown next to AirDay's hourly view and never feeds any rule.
- The daily brief runs on AWS automatically on school days. At most one automatic email per day, retried if sending fails, never a silent failure.

Non-goals (hackathon)
- No sensors or hardware.
- General guidance based on public advisories, not medical advice for individual children. Moving indoors reduces exertion; it does not make indoor air clean.
- No SMS (SNS SMS to India needs DLT registration). Email only; WhatsApp is copy-paste now and on the roadmap as an integration.
- No login. One demo school, an admin key for write endpoints (§10).
- No per-school rule tuning (P2).
- AirDay doesn't replace GRAP orders or government school closures.

## 5. Success metrics

Demo
- Profile setup under 1 minute; timetable import (CSV/paste or "Use sample timetable") under 2 minutes.
- **Outsider test, Saturday at DTU:** 3 people outside the team each read the email and answer "What happens to Class 6B's PE today?" within 30 seconds. Pass: 3 of 3.
- Real scheduled runs on Fri and Sat at 06:00, shown by a CloudWatch log line.
- A duplicate invocation sends no second email; an SES failure is retried (tested, §13).
- Every brief action has a rule ID that exists in `rules.yaml`, enforced at runtime (an invalid brief is not emailed) and in tests.
- Every chat answer that evaluates an activity cites at least one rule ID returned by a tool in that turn.

Pilot (after the hackathon): brief open rate, parent notes copied, and outdoor minutes moved out of Very Poor or worse hours.

## 6. Features

### Must (never cut)
1. **School profile.** Name, locality search (Open-Meteo geocoding finds place names, not street addresses) plus editable lat/lon, school hours, school days (default Mon–Sat), holidays, principal email, CPCB station, OpenAQ location. Public `GET /school` never returns the email.
2. **Timetable.** CSV/paste import (`day,start,end,type,label`), "Use sample timetable", and a small editable table. Validation: `day` ∈ Mon–Sun, `type` ∈ assembly/recess/pe, `HH:MM` 24-hour times, `start < end`, within school hours, at most 200 rows, BOM and header row tolerated. Invalid rows are shown with the reason and not saved. The sample puts a morning PE period on every school day.
3. **Forecast ingest.** Hourly PM2.5 and PM10 from the Open-Meteo Air Quality API (CAMS Global) with `timezone=Asia/Kolkata` and explicit `start_date`/`end_date`.
4. **Station readings.** Hourly-average PM2.5 and PM10 (µg/m³) for the nearest reference station via OpenAQ v3, for every hour since midnight. Used for the dashboard overlay and for escalation (§7.6).
5. **Official AQI headline.** From the data.gov.in CPCB real-time feed: a 24-hour rolling station value with its `last_update` time, labelled "as of HH:MM". The feed is per pollutant; the station AQI is the highest sub-index, computed only if at least 3 pollutants are reported and one is PM2.5 or PM10 (CPCB rule). Display only.
6. **Indicative GRAP stage.** Derived from the Delhi average AQI (mean of Delhi station AQIs; in replay, the CPCB bulletin city value): I 201–300, II 301–400, III 401–450, IV >450. Always labelled "Indicative (from Delhi average AQI, not a CAQM order)". An admin can set the official stage; the override expires after 3 days.
7. **Rules engine.** Pure function of (timetable, hourly data, station readings, date, now) → actions. Activity-bound actions (assembly, recess, PE) and hour-bound actions (windows, parent note). All rule data in `rules.yaml` (§7.5).
8. **Validator at runtime.** Every action has rule IDs that exist; every timetable activity of the day has exactly one action; no hourly number is labelled "AQI". A brief that fails is not emailed; the principal gets "We couldn't build today's plan; check the official AQI" instead, and the team gets an alarm.
9. **Daily brief.** EventBridge Scheduler, `cron(0 6 ? * * *)` in `Asia/Kolkata`, triggers the brief Lambda. It skips non-school days and holidays (and logs the skip), builds and validates the brief, and sends the email through SES using the send protocol in §9.2.
10. **Historical replay.** Pick a past date from a fixed list. The pipeline runs "as of 06:00" on that date from frozen fixtures, so the video and golden test don't depend on live APIs. Stored as `REPLAY#<date>`, never touches real briefs or the email lock. An admin can email a replay with "REPLAY" in the subject (used in the video).
11. **Parent note, English and Hindi, from templates.** Per-rule templates in `rules.yaml`. A fluent Hindi speaker reviews every Hindi template. "Copy for WhatsApp" copies plain text.
12. **Dashboard: Today.** Decision headline, "What changes today" first, "As normal" collapsed, official AQI and GRAP badge with labels, hour-by-hour PM2.5 strip with station overlay and a text table, parent note with English/Hindi toggle and copy button, replay picker. Meets §11.

### Should (cut in this order if behind)
13. **Principal chat** (Strands agent). Tools: `get_day(date)` (forecast + official AQI) and `evaluate_activity(type, date, start, end)`. Behaviour in §8.2.
14. **Free-text addition, translated.** The principal types one line to append to the parent note; the agent translates it; the validator in §8.3 checks it; she sees both versions and confirms. It updates the dashboard note, not an email already sent.
15. **"Check an activity" form.** Deterministic `GET /evaluate`, shared with the chat tool. If chat is cut, this keeps the event-planning demo.

Cut order: chat → free-text translation. The form, replay, official AQI, station overlay, validator and scheduled email are never cut. If every LLM job is cut, Strands is no longer used, and AWS eligibility rests on the deployed services and SAM CLI.

### P1
- 3-day outlook strip.
- An "outdoor minutes moved" counter across real and replayed days.
- A 07:15 update email if escalation changes the plan.

### P2
- WhatsApp integration, logins (Cognito), multiple schools, district view, per-school strictness, indoor sensors, automated GRAP tracking.

## 7. Rules

### 7.1 Two quantities, never mixed

| Quantity | Source | Used for |
|---|---|---|
| Hourly PM2.5/PM10 (µg/m³) | Open-Meteo forecast; OpenAQ station hourly averages | All timetable decisions and escalation |
| Official AQI (24-hr basis) | data.gov.in (live); CPCB bulletin fixture (replay) | Headline and indicative GRAP only |

CPCB defines its breakpoints on 24-hour averages. Applying them to hourly values is AirDay's own cautious choice, not CPCB's method, and the "About the data" page says so. An hourly number is never labelled "AQI". When the two seem to disagree the brief explains it: "Daily average is Poor; this morning's peak is in the Very Poor range."

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
- Everything is in IST (Asia/Kolkata). OpenAQ returns UTC and is converted on ingest; an OpenAQ hourly average is assigned to the hour it starts in.
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

`backend/rules/SOURCES.md` lists each source key with `status` (`pending`/`read`), `read_by` and `read_on`. A release test (`RELEASE=1 pytest`) fails while any emitted rule cites a pending source. Deadline: Fri 18:00. A rule whose source isn't read by then is reworded as plain guidance with `basis: derived`.

Sources to read (none cited until read): CPCB National AQI (2014) health statements; CAQM GRAP schedule (current revision); WHO or US EPA guidance on reducing exertion during high-pollution episodes. The CPCB "Moderate" statement wording must be checked; it may not mention children and older adults.

### 7.6 Data limits and escalation
- Open-Meteo air quality uses CAMS Global at about 0.4° (40–45 km). Delhi NCR is one or two grid cells: "city-area forecast".
- Past data comes from the same Air Quality endpoint with `start_date`/`end_date` (archived CAMS forecasts, available from about August 2022), not the weather archive API.
- CAMS is known to under-predict Delhi winter peaks. Escalation: take the latest OpenAQ hourly reading no older than `STATION_MAX_AGE_MIN` (default 120, set from a Thursday lag measurement). If its band is worse than the forecast band for the reading's hour, apply the station band to that hour and the next 2, marked "escalated: station reading". Escalation only raises a band. It also fills `unknown` hours.
- The email is a snapshot "as of 06:00". The dashboard recomputes on load (upstream cached 10 min) and shows "Changed since this morning's email" when a band has moved.
- Data attribution (CAMS/Open-Meteo, OpenAQ, data.gov.in/CPCB) appears in the email footer and the dashboard.

### 7.7 Replay fixtures
`fixtures/replay/<date>.json` holds the frozen Open-Meteo response, OpenAQ hourly readings if available, and the CPCB bulletin city AQI. The bulletin is published around 4 PM, so the replay shows the previous day's city value (what was known at 06:00), labelled "Delhi AQI 4xx, CPCB bulletin, <date>". Replay date criteria: a school day, schools not ordered shut, a Very Poor morning and a better afternoon in the fixture, and archive coverage for the next day so chat works. Pick one main date and one backup on Thursday by fetching the data, not from memory.

## 8. Agent

### 8.1 Provider
Strands Agents SDK (AWS open source), provider set by `MODEL_PROVIDER`. Bedrock has no free tier for models; usage draws on the account's credits, and a weekend of testing should cost well under $1. The bake-off (Thursday, by 18:00) runs 5 Hindi translations and 5 tool-calling prompts on Amazon Nova Lite, then Nova Pro, via the APAC cross-region inference profile or us-east-1. Pass bar: 4 of 5 on each. Fallback: Strands' LiteLLM provider with any capable model. The video names whichever provider is used.

### 8.2 Chat
- Context date: the dashboard's selected date (live or replay). "Today" and "tomorrow" are relative to it. Planning window: context date plus 2 days; outside that gets a fixed reply.
- Events (sports day, excursion) are evaluated as PE.
- Output is structured JSON `{answer, ruleIds}`. If `evaluate_activity` was called, `ruleIds` must be non-empty, and every ID must have come from a tool in that turn. One retry, then the raw tool result is shown.
- At most 4 tool calls; 20 s budget; Lambda timeout 25 s (HTTP API limit is 30 s). Input capped at 500 characters; last 6 messages sent by the client; nothing stored.
- Medical questions get a fixed reply pointing to a doctor. Tools are read-only, so prompt injection can at worst produce a bad answer, which the grounding check mostly catches.

### 8.3 Translation check
Normalise Devanagari digits (०–९) to ASCII; every number and `HH:MM` time in the English must appear in the Hindi; at least 60% of letters must be Devanagari; length 0.5×–2.5× of the English; at most 300 characters. On failure the addition stays English-only with a visible note.

## 9. Architecture

```
EventBridge Scheduler (06:00 IST daily)
        │
        ▼
Lambda: brief ──► Open-Meteo · OpenAQ · data.gov.in
   │  rules engine + validator (airday package)
   ├─► DynamoDB (school, timetable, cache, briefs, replays, email state, counters)
   └─► SES → principal

Next.js (static export) on Amplify Hosting
   └─► API Gateway HTTP API
         ├─► Lambda: api    (school, timetable, brief, replay, evaluate)
         └─► Lambda: agent  (chat, translate; Strands)
CloudWatch alarm on brief failures → SNS email to the team
```

AWS services: Lambda, EventBridge Scheduler, DynamoDB, SES, API Gateway, Amplify Hosting, CloudWatch, SNS (team alarms only), SSM Parameter Store, Bedrock (if chosen). AWS open source: SAM CLI, Strands Agents SDK.

### 9.1 Stack and repo layout
- Backend: Python 3.12, `uv`, `pytest`. One package `airday` shared by all Lambdas; the engine has no AWS imports. A local dev server (`uv run python -m airday.devserver`) serves the same API from an in-memory store, so the frontend can be built without AWS.
- Frontend: Next.js (App Router, TypeScript), static export.
- Infrastructure: one SAM template.

```
/backend
  /airday        engine, rules loader, aqi, validator, sources, store, email, api, agent
  /handlers      brief.py, api.py, agent.py
  /rules         rules.yaml, SOURCES.md
  /tests
/contracts       brief.schema.json (frozen Thu 18:00; additive changes only after)
/fixtures        /replay/<date>.json, /dashboard/brief.sample.json
/frontend        Next.js app
template.yaml
```

### 9.2 Email send protocol
`EMAIL#<date>` item with `status` ∈ SENDING/SENT/FAILED and `attempts`.
1. Claim with a conditional put: item absent, or `status = FAILED` and `attempts < 3`. If the claim fails, exit (already sent or in progress).
2. Send through SES. On success set SENT; on error set FAILED and raise so the Scheduler retries (2 retries, 5 min apart).
3. A SENDING item older than 10 minutes is left alone and alarmed. The remaining edge case: a crash after SES accepted the message but before SENT is recorded produces no second email, so the guarantee is "at most one automatic email per day, retried on known failure".

Manual regenerate rebuilds the brief and only emails with `resend=true` (admin). Replays never take the lock.

### 9.3 Upstream failures
Every call has a 5 s timeout and one retry. Open-Meteo down: use the cached forecast for the date, marked "cached from HH:MM"; none cached: "Forecast unavailable today" email. OpenAQ or data.gov.in down: the field is shown as unavailable and the brief still runs. One structured JSON log line per run (date, bands, rule IDs, escalations, upstream status, email status).

## 10. API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/school` | public | Profile without email |
| PUT | `/school` | admin | Update profile, GRAP override |
| GET | `/activities` | public | Timetable |
| PUT | `/activities` | admin | Replace timetable (CSV or JSON); per-row errors |
| GET | `/brief?date=` | public | Stored live brief |
| GET | `/brief/live` | public | Recomputed now, with diff against the stored brief |
| POST | `/brief/regenerate?date=&resend=` | admin | Rebuild; email only if `resend=true` |
| GET | `/replay/dates` | public | Available replay dates |
| GET | `/replay?date=` | public | Replay brief |
| POST | `/replay/email?date=` | admin | Send a REPLAY-labelled email |
| GET | `/evaluate?type=&date=&start=&end=` | public | Deterministic activity check |
| POST | `/chat` | public, capped | Chat (agent Lambda) |
| POST | `/note/translate` | admin, capped | Free-text translation (agent Lambda) |

Admin key: random 32-byte value in SSM SecureString, checked with a constant-time compare. The dashboard Settings page stores it in `sessionStorage` with a "Forget key" button. Chat and translation share a hard daily cap (`COUNTER#<date>`, 200 calls) plus HTTP API throttling on those routes (1 rps, burst 3) and a $5 AWS Budgets alert. CORS allows the Amplify domain and `localhost:3000`; CORS is not protection, the key and caps are. Fine for a hackathon, not production.

## 11. Accessibility and design
- Band colours always carry the band name as text; the hourly strip has a text-table alternative.
- WCAG 2.1 AA contrast (4.5:1 body text); keyboard-reachable controls with visible focus; labelled fields.
- Email reads correctly with images off and has a plain-text part.
- Hindi text has `lang="hi"`. Times are 24-hour `HH:MM`. Plain words, no jargon.
- Works at 360 px wide.

Full WCAG validation needs manual testing with assistive technology; these rules are the baseline, not a compliance claim.

## 12. Data model (DynamoDB single table)

| PK | SK | Attributes |
|---|---|---|
| `SCHOOL#demo` | `PROFILE` | name, locality, lat, lon, start, end, schoolDays[], holidays[], principalEmail, cpcbStation, openaqLocationId, grapOverride {stage, setAt, expiresAt} |
| `SCHOOL#demo` | `ACTIVITY#<id>` | day, start, end, type, label |
| `SCHOOL#demo` | `CACHE#<source>#<date>` | raw response, fetchedAt (TTL 2 days) |
| `SCHOOL#demo` | `BRIEF#<date>` | brief JSON (schemaVersion, rulesVersion, mode=live) |
| `SCHOOL#demo` | `REPLAY#<date>` | brief JSON (mode=replay) |
| `SCHOOL#demo` | `EMAIL#<date>` | status, attempts, updatedAt, messageId |
| `COUNTER#<date>` | `AGENT` | n (TTL 7 days) |

`contracts/brief.schema.json` is the contract between backend and frontend; the sample fixture and live responses both validate against it in tests.

## 13. Testing

| Area | Tests |
|---|---|
| Bands | Boundaries 30 / 30.01 / 90.4 / 250 / 250.01 and PM10 equivalents; null, negative and >1000 values; both missing → unknown |
| Time | Two-hour overlap takes the worse band; ending on the hour doesn't touch the next; unknown + Very Poor stays Very Poor; unknown + Moderate is unknown; UTC→IST |
| Rules file | 35 cells, no duplicates, emitted notes have Hindi, source keys exist; release test for read sources |
| Escalation | Raises only; fills unknown; ignored when stale; covers exactly 3 hours |
| Brief | One action per activity; window runs merged by instruction; one parent note; changes first; subject line |
| Email | Duplicate invocation → one send; SES failure → FAILED then retry → SENT; attempts cap |
| Validator | Rejects unknown or missing rule IDs, a missing activity, "AQI" next to an hourly number |
| Official AQI | Max sub-index; fewer than 3 pollutants → unavailable; GRAP thresholds; override expiry |
| Translation | Devanagari digits accepted; missing number or time rejected; Latin-only output rejected |
| Chat grounding | Uncited evaluation rejected; foreign rule ID rejected |
| Contract | Sample fixture and API responses validate against the schema |
| Golden | The hero replay date produces the stored expected brief |

## 14. Timeline (from Thu 14:00 IST)

Roles: **Backend** (engine, API, email), **Data & infra** (sources, SAM, AWS, schedule), **Frontend** (Next.js), **Rules & content** (rules, sources, Hindi, replay dates, video, blog).

| When | Milestone |
|---|---|
| Thu 14:00–16:00 | Everyone verifies as a student on AWS Builder Center. Read the Rules page for the deadline time and submission format. Repo, engine skeleton, frontend skeleton. |
| Thu 18:00 | Schema frozen. Provider bake-off decided. Replay dates and fixtures picked. SES sender and recipients verified. OpenAQ lag measured. data.gov.in field meaning checked. |
| Thu 23:00 | Thin pipeline deployed: scheduled brief with template note and email. First real run Fri 06:00. |
| Fri 13:00 | End-to-end gate: dashboard on Amplify reads the live API; replay works. |
| Fri 18:00 | Sources read or rules reworded. Hindi templates reviewed. |
| Fri 22:00 | Feature freeze. Chat, translation and the check form in or cut. |
| Sat (DTU) | Polish only. Sat 06:00 real run captured. Outsider test. 10-second clip with consent. Rough cut of the video in the evening. |
| Sun | Golden test, final video (aim 2:50), Builder Center blog, submit by 18:00 internal deadline. |

## 15. Demo video (3 minutes)

| Time | Shows | Criterion |
|---|---|---|
| 0:00–0:20 | Teacher or parent clip (with consent), smoggy assembly (own or licensed footage) | Impact |
| 0:20–0:40 | Sunita sets the locality, pastes the timetable; one invalid row is rejected | Usability |
| 0:40–1:40 | Replay date: the REPLAY email arrives with the decision in the subject; dashboard with official AQI and GRAP labels, hourly strip with station overlay and an escalated hour, "Class 6B PE: indoors [R-VP-PE]", Hindi note copied to WhatsApp | Impact, usability, execution |
| 1:40–2:10 | "Can we hold sports day tomorrow afternoon?" The answer cites a rule | Execution |
| 2:10–2:35 | Architecture diagram, EventBridge schedule, SAM template, CloudWatch log line from the real Sat 06:00 run | Built on AWS |
| 2:35–2:50 | Validator tests passing, "every action traces to a cited rule", what's next | Execution |

Rule IDs stay visible in every frame that shows a brief.

## 16. Risks

| Risk | Mitigation |
|---|---|
| CAMS under-predicts or Open-Meteo is down | Station escalation; cached forecast; "unavailable" email |
| OpenAQ lag makes escalation never fire | Measure Thursday; configurable max age; "no recent station reading" shown |
| data.gov.in fields mean something else | Thursday check; station AQI shown only when computable |
| Replay date has weak values | Pick from fetched data; backup date |
| Only one real run before the video | Thin pipeline live Thu night |
| Provider unavailable or weak Hindi | Bake-off; notes are templates and unaffected; chat is cuttable |
| Chat ungrounded advice | Structured output, rule-ID check, retry, raw tool result |
| SES lands in spam | Verified domain sender with DKIM if available; test inboxes Thursday |
| Sources not read in time | Fri 18:00 deadline; reword as derived guidance |
| Public endpoints drain credits | Daily cap, throttling, budget alert |
| Student verification missed | Thursday task for everyone |

## 17. Open questions
- Product name (AirDay is a placeholder).
- Who attends DTU on Saturday. The plan holds either way.

## 18. Changes from previous version
Merged from a 16-way review of the previous draft.
- **Timeline** re-based to Thu 14:00 with four roles, a thin pipeline live Thursday night (real runs Fri and Sat), Fri 22:00 feature freeze, and student verification on Thursday.
- **Email** "exactly once" replaced by a claim-then-send protocol with retries; the guarantee is now stated as at most one automatic email, never a silent failure.
- **Replay** separated from real briefs (`REPLAY#<date>`, own endpoints, REPLAY email), frozen fixtures, chat relative to the selected date, demo question changed to "tomorrow afternoon".
- **Facts corrected:** geocoding finds place names; HTTP API limit is 30 s; past air-quality data comes from the same endpoint with dates (from ~Aug 2022); CAMS is ~40–45 km and 3-hourly; Bedrock has no model free tier; GRAP is based on Delhi's average AQI; data.gov.in is per-pollutant, so the station AQI is computed with CPCB's 3-pollutant rule; the bulletin is city-level and published around 4 PM.
- **Rules** made complete (35 cells, unknown rows, explicit no-note rules), single decisions for Poor PE and Severe PE, fail-safe unknown handling, window merge by instruction, `basis` and source status with a release test.
- **Validator** runs at runtime and blocks a bad email.
- **Chat** uses structured output for a mechanical grounding check; a deterministic "Check an activity" form backs it up.
- **Translation** check handles Devanagari digits and script.
- **Usability:** decision in the subject line, changes first, Copy for WhatsApp, measured outsider test.
- **Privacy:** public profile hides the email; GRAP override expires.
- **Stack:** Next.js frontend, Python backend with a local dev server.
