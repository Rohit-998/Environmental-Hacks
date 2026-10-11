# AirDay — demo video script (≤3 min)

Target: **2:45**. Narration is word-for-word; "Show" is what to have on screen. Speak at a steady pace
(~150 words/min). Record the screen in the browser at 1280×800+; a plain voiceover is fine.

## Before you record

- Open the live site: https://main.d2ji7br4eqzndl.amplifyapp.com
- Make sure `DEMO_ADMIN` is on (so the demo school works on camera) — leave the admin key handy if needed.
- Have two tabs ready: **Today** and **Check an activity**.
- Know your replay date: **2025-11-19** (a Severe Delhi morning).
- Do one dry run of the "Find a clear window" and the assistant question so there's no waiting on camera.

---

## 0:00 – 0:15 · Hook

**Show:** the Today page, scrolled to the top.

**Say:** "On a Delhi winter morning, the air can be hazardous before the first bell — but the one number everyone
checks, the AQI, is a 24-hour average that lags the morning. This is AirDay. It tells a school what to do about the
air, today, period by period."

## 0:15 – 0:40 · Today

**Show:** the morning plan and the hourly chart.

**Say:** "This is a school's live morning plan. AirDay takes the hourly pollution forecast for the school's
locality and walks its real timetable — assembly, recess, PE — and tells the principal what to do with each. The
chart is hourly PM2.5: real concentrations, which AirDay never calls 'AQI', because AQI is a daily average."

## 0:40 – 1:20 · Replay a Severe day (the core)

**Show:** switch "Plan from" to **Replay: 2025-11-19**. Let the red plan load; scroll the activity rows, then the
parent note.

**Say:** "But the point of AirDay is the bad days — so let me replay a real one. The 19th of November: a Severe
morning in Delhi, frozen with the actual forecast, a real station reading, and the official bulletin. Watch the
plan. Assembly — hold indoors. Recess — keep the children in. PE and the Class 6B match — moved indoors, Severe.
Every line carries the rule behind it, traceable to a CPCB health source. And the parent note is already written,
English and Hindi, ready to send. The principal gets all of this by email at 6 a.m., before anyone leaves home."

## 1:20 – 1:50 · Find a clear window

**Show:** the **Check an activity** page, scroll to **Find a clear window**. Pick PE, 2 hours, click **Find
windows**. (Live mode shows real clear windows; keep it on "Today" here, not replay.)

**Say:** "The harder question is: when *can* we hold the sports day? AirDay answers that too. I pick PE and two
hours, and it scans the next three days, within school hours, and shows exactly when the air is clear enough — with
the band and the rule. That's planning around the air, not just reacting to it."

## 1:50 – 2:15 · The assistant

**Show:** open the chat, type: **"When can we hold sports day this week?"** Let the grounded answer appear.

**Say:** "There's also an assistant. I'll ask it in plain English — when can we hold sports day this week? It calls
the same rules engine and answers with the window — and it can only cite rules the engine actually returned, so it
can't make up a number about the air."

## 2:15 – 2:45 · AWS + proof + close

**Show:** the architecture diagram in the repo README (or the CloudWatch dashboard), then back to the site.

**Say:** "Behind this, it's all serverless on AWS. At 6 a.m. a scheduler fans out one job per school through SQS to
Lambda workers — so a thousand schools cost one forecast fetch, not a thousand. Cognito keeps each principal to
their own school, and everything's traced and alarmed in CloudWatch. And it's measured: against nine Delhi
stations, flooring the forecast with live readings catches ninety-three percent of the worst hours. AirDay — the
air, turned into a plan a school can act on. Thanks for watching."

---

## Notes

- If live air is clean and the window finder shows mostly "Moderate" windows, that's fine — it proves the positive
  case. The replay segment already carries the dramatic "all red" moment.
- Keep the whole thing under 3:00; the Rules require ≤3 minutes. If you run long, trim the Today segment (0:15–0:40)
  first — the replay and the window finder are the parts that win.
- Record in one take per segment and stitch; or do a single take following the timings above.

