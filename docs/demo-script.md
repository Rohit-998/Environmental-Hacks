# AirDay — demo video script (final · ≤3 min)

Target **2:45**. Narration is word-for-word; **OPEN** = what's on screen. Speak ~150 words/min.

## The setup (lock these in)

- **Record the LIVE site:** https://main.d2ji7br4eqzndl.amplifyapp.com
- **Stay on the public demo school — do NOT sign in** (live sign-up sends an email code; it's a guaranteed stall).
- **Replay day = Wed, 19 Nov** (Severe, AQI 374 — the dramatic one). You switch to it mid-video.
- Tabs ready: **Today's plan** and **Check an activity**. Confirm the top-left "API status" reads **Operational**.
- Do one silent dry-run of: the chat question, the "Plan from → Wed, 19 Nov" switch, and the window finder.

---

## Timeline

### ⏱ 0:00–0:12 · Hook
**OPEN:** Today's plan page (as it loads, live).
**SAY:** "A Delhi winter morning can turn hazardous before the first bell — but the AQI everyone checks is a
24-hour average that lags the morning. This is AirDay: it tells a school what to do about the air, today,
period by period."

### ⏱ 0:12–0:40 · It's live right now
**OPEN:** stay on Today's plan (it's a Sunday — the "not a school day" banner and the hourly chart are visible).
**SAY:** "This is running live. Today's a Sunday, so AirDay knows there's no school and sends nothing — it only
emails on school mornings. But you can still see the live picture: hourly PM2.5 for the school's area, in the
moderate range today, hour by hour. Real concentrations — AirDay never calls an hourly number 'AQI', because AQI
is a daily average."

### ⏱ 0:40–1:05 · The assistant
**OPEN:** scroll down to the chat box on the Today page. Type: **When can we hold sports day this week?**
**SAY:** "There's an assistant for planning. I'll ask in plain English — when can we hold sports day this week? It
calls the same rules engine and answers with the clear windows, and it can only cite rules the engine actually
returned, so it can't invent a number about the air."

### ⏱ 1:05–1:45 · Replay a real Severe day (the peak)
**OPEN:** top-right "Plan from" → **Wed, 19 Nov**. Let the red plan load; scroll the activity rows, then the note.
**SAY:** "Now the day that matters. I switch to the 19th of November — a Severe Delhi morning, frozen with the
real forecast, a real station reading, and the official CPCB bulletin: AQI 374. Watch the plan go red. PM2.5
peaks around 187, deep in the Severe range. Assembly — hold indoors. Recess — hold indoors. Both PE periods —
cancelled, moved into a classroom. Every line names the rule behind it, traceable to a CPCB health source, and
the parent note is already written, English and Hindi. The principal gets all of this by email at 6 a.m., before
anyone leaves home."

### ⏱ 1:45–2:15 · Find a clear window
**OPEN:** left nav → **Check an activity** → scroll to **Find a clear window**. Leave "Plan from" on **Today**.
Pick **PE**, **2 hours**, click **Find windows**.
**SAY:** "And the flip side — when is it safe? On Check an activity, I pick PE and two hours, and AirDay scans the
next three days, within school hours, and shows exactly when the air is clear enough — with the band and the
rule. Planning around the air, not just reacting to it."

### ⏱ 2:15–2:45 · Built on AWS + proof + close
**OPEN:** the architecture diagram in the repo README (or the CloudWatch dashboard), then back to the site.
**SAY:** "Behind this, it's all serverless on AWS. At 6 a.m. a scheduler fans out one job per school through SQS
to Lambda workers — so a thousand schools cost one forecast fetch, not a thousand. Cognito keeps each principal
to their own school, and everything's traced and alarmed in CloudWatch. And it's measured: against nine Delhi
stations, flooring the forecast with live readings catches ninety-three percent of the worst hours. AirDay — the
air, turned into a plan a school can act on. Thanks for watching."

---

## If something looks different on the day

- **The live band isn't "moderate."** Just say what's on screen ("in the good range", "poor today") — the point is
  that it's live, not the exact band.
- **"Delhi AQI — unavailable"** on the live view is the government feed being down (handled, reference-only). Don't
  mention it; the 19 Nov replay shows a real AQI (374) instead.
- **The assistant is slow or busy** (free-tier model): wait a beat, or re-ask once. If it still stalls, cut that
  segment — the window finder shows the same planning power visually, and you stay under 3:00.
- **Keep it under 3:00** (hard rule). If you're long, trim the "It's live right now" segment first; the replay and
  the window finder are what win.
- Record per-segment and stitch, or one take top-to-bottom. Only one on-camera switch (Plan from → 19 Nov) and one
  page change (→ Check an activity); everything else is scrolling.
