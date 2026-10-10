# AirDay — AWS Builder Center content

Paste-ready content. Recommended: publish as an **Article** (richer, discoverable); optionally also drop a short
**Post** into the Environmental Hacks hackathon space linking to it.

Replace these links before publishing:
- Live demo: https://main.d2ji7br4eqzndl.amplifyapp.com
- Code: https://github.com/Rohit-998/Environmental-Hacks
- Video: _(YouTube link — add after recording)_

---

## ARTICLE

**Title** (≤255 chars):

```
AirDay: a 6 AM air-safety plan for schools, built serverless on AWS
```

**Description** (≤512 chars):

```
I built AirDay for the AWS Environmental Hacks hackathon: it reads the hourly PM2.5 forecast for a school's
locality, checks it against the school's outdoor timetable, and emails the principal a period-by-period plan at
6 AM — what to move indoors today, and when the air is clear enough to hold it. Here's the AWS architecture, the
decisions behind it, and what a backtest against Delhi stations taught me.
```

**Tags** (pick ≤5 from the list, closest to): Serverless · AWS Lambda · Amazon DynamoDB · Hackathons · Generative AI

**Cover image** (optional, 1200×675): a screenshot of the replayed **19 Nov** plan — the red "move indoors" view.

**Body** (paste everything below into the Body field):

<!-- BODY_START -->
## The problem

On a Delhi winter morning the air is often hazardous before the first bell. But the number everyone checks — the
official AQI — is a **24-hour average** that lags the morning badly, and the school about to run an outdoor PE
period is the last to know. I wanted to answer one question for one person: **what should this school change
outdoors today, and why?**
## What AirDay does

Every school day at 6 AM, for each school, AirDay:

- pulls the **hourly PM2.5/PM10 forecast** for the school's locality,
- walks that school's **own outdoor timetable** — assembly, recess, PE,
- and emails the principal a **period-by-period plan**: this proceeds, that moves indoors, from these hours, with
  the reason — plus a parent note in **English and Hindi**.

Two more pieces I'm glad I added:

- **"Find a clear window"** — the inverse question: *when can we hold sports day?* It scans the next 3 days within
  school hours and lists the stretches when the air is clear enough.
- **A grounded assistant** — ask "can we do the 2 PM match tomorrow?" in plain English. It uses read-only tools
  over the same rules engine and can only cite rules the engine actually returned, so it can't invent a number
  about the air.

You don't need a bad-air day to see it work: the live demo lets you **replay 19 Nov 2025**, a real Severe Delhi
morning (frozen with the actual forecast, a station reading, and the official bulletin), and watch the plan turn
red period by period.

👉 **Live demo**, **code**, and a **3-min video** — links at the top.

## How it's built — all serverless on AWS

The whole thing is one AWS SAM / CloudFormation stack, auto-deployed from GitHub via OIDC (no stored keys):

```
6 AM IST → EventBridge Scheduler → Planner Lambda → SQS (one job per school) → Worker Lambdas → SES email
                                         |                                            |
                                 one forecast fetch                          build + validate the plan,
                                 per ~40 km grid cell                        store it, email the principal
```

- **AWS Lambda** runs the rules engine, API, planner and worker (Python 3.12).
- **Amazon SQS** fans out one message per school, with a dead-letter queue and capped concurrency. A shared
  per-grid-cell forecast cache in **DynamoDB** means a city of 1,000 schools costs **one** forecast fetch, not 1,000.
- **Amazon API Gateway (HTTP API)** fronts it with an **Amazon Cognito** JWT authorizer, so each principal only
  ever sees their own school.
- **Amazon DynamoDB** single table (on-demand, PITR, TTL); **Amazon SES** for email (at-most-once send);
  **SSM Parameter Store** for every secret; **CloudWatch** dashboard + alarms, **AWS X-Ray** tracing, **SNS**
  alerts, **AWS Budgets** cost guard; **AWS Amplify Hosting** serves the Next.js dashboard. Observability and the
  assistant are built on AWS open source — **Powertools for Lambda** and the **Strands Agents SDK**.
## Three decisions I'd defend to a reviewer

1. **Decide on concentrations, not AQI.** The official AQI is a 24-hour average; applying it to a single hour is
   simply wrong. AirDay bands on **hourly PM2.5/PM10 concentrations** and never calls an hourly number "AQI".
2. **Rules as data.** 35 rules (7 air bands × 5 activities) live in one `rules.yaml`; the engine, validator,
   dashboard and tests all read it, and every rule cites a health source. A release test blocks shipping if any
   emitted rule cites a source nobody has read.
3. **Trust, but verify against reality.** A backtest scores the engine against **9 Delhi stations** (Oct–Dec 2025).
   The forecast alone caught 30% of Very-Poor-or-worse hours — CAMS reads ~100 µg/m³ cleaner than Delhi stations in
   winter. Flooring the day at the latest live station reading lifts the catch rate to **93%**, and that result
   changed the design.

## The honest part: Gemini, not Bedrock

I wanted the assistant on Amazon Bedrock. But on a brand-new AWS account, **Bedrock model invocation is blocked** —
every model returns `ValidationException: Operation not allowed`. Rather than fake it, I wired the agent through the
Strands Agents SDK with a `ModelProvider` switch and ran it on Google Gemini for the demo. Moving to Bedrock is one
deploy parameter, not a code change. If you're building on a new account, plan for this — Bedrock access isn't
instant.

## Cost

Per school per month (26 school days): under **$0.01** without chat — the forecast fetch is shared, the worker runs
about a second a day, and one email goes out. The fixed pieces fall inside free tier.

## What I learned

- Fan-out plus a shared cache turns a per-tenant workload into a near-constant one.
- Being honest about limits is a feature: AirDay says the forecast is city-area (~40 km), floors it with the
  nearest station, and never overclaims the air at one gate.
- A backtest number ("93%") is worth more than any adjective.

Built solo for Environmental Hacks (Air track). Feedback welcome — links at the top.
<!-- BODY_END -->

---

## SHORT POST (companion, or use instead of the article)

**Post to:** Environmental Hacks (the hackathon)

**Title** (≤100 chars):

```
AirDay — a 6 AM air-safety plan for schools (my Environmental Hacks build)
```

**Body:**

```
I built AirDay for Environmental Hacks (Air track): it reads the hourly PM2.5 forecast for a school's locality,
checks it against the school's outdoor timetable, and emails the principal a period-by-period plan at 6 AM — what
to move indoors today, with a parent note in English and Hindi. It also finds clear windows for a sports day, and
has a grounded assistant that can only cite the rules behind its answers.

All serverless on AWS — Lambda, SQS fan-out, DynamoDB, Cognito, API Gateway, SES, EventBridge Scheduler,
CloudWatch/X-Ray — in one SAM stack, auto-deployed via GitHub OIDC. It decides on hourly concentrations (not the
24-hour AQI), keeps every rule traceable to a health source, and a backtest against 9 Delhi stations catches 93%
of the worst hours.

Try the replay of a real Severe Delhi morning:
🔗 Live demo: <link>
💻 Code: <link>
🎥 Video: <link>
```


