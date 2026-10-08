"""06:00 fan-out: one planner, many workers.

  EventBridge Scheduler ─► planner Lambda ─► SQS (one message per school) ─► worker Lambda (batch, partial failures)
                                                                              └─► DLQ after 3 receives

The planner warms the shared forecast cache once per CAMS grid cell before queueing, so N schools in one city
cost one Open-Meteo call. Workers are idempotent: the brief write is an overwrite and the email is protected by
the EMAIL#<date> claim, so SQS at-least-once delivery never sends a second email.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from collections.abc import Callable, Iterable
from typing import Any

from . import mailer, service
from . import school as schoolmod
from . import timeutil as tu
from .store import Store
from .validator import BriefInvalid

log = logging.getLogger("airday")

SEND_CUTOFF = os.environ.get("SEND_CUTOFF", "07:30")
SQS_BATCH = 10


def plan(store: Store, date: dt.date, enqueue: Callable[[list[dict]], None]) -> dict[str, Any]:
    """Warm one forecast per grid cell, then enqueue one job per school. Returns a summary for the log line."""
    schools = service.list_schools(store)
    cells: dict[str, tuple[float, float]] = {}
    for s in schools:
        p = service.get_profile(store, s["schoolId"])
        g, glat, glon = service.grid_key(p["lat"], p["lon"])
        cells.setdefault(g, (glat, glon))
    warmed = {}
    for g, (lat, lon) in cells.items():
        try:
            warmed[g] = service.warm_forecast(store, lat, lon, date)
        except Exception as e:  # workers fall back to their own fetch, then to "forecast unavailable"
            warmed[g] = f"failed: {e}"
            log.error("forecast warm failed for %s: %s", g, e)
    jobs = [{"schoolId": s["schoolId"], "date": date.isoformat()} for s in schools]
    for i in range(0, len(jobs), SQS_BATCH):
        enqueue(jobs[i:i + SQS_BATCH])
    return {"date": date.isoformat(), "schools": len(jobs), "gridCells": len(cells), "warm": warmed}


def run_job(store: Store, job: dict, now: dt.datetime,
            send: Callable[[str, str, str, str], str] | None, dashboard_url: str = "") -> dict[str, Any]:
    """Build, store and email one school's brief. Raises to let SQS retry; the email claim makes retries safe."""
    school_id, date = job["schoolId"], dt.date.fromisoformat(job["date"])
    profile = service.get_profile(store, school_id)
    base = {"event": "daily_brief", "schoolId": school_id, "date": date.isoformat()}

    if not schoolmod.is_school_day(profile, date):
        return base | {"skipped": True, "reason": "not a school day"}
    if now.date() == date and now.strftime("%H:%M") > SEND_CUTOFF:
        return base | {"skipped": True, "reason": f"after send cutoff {SEND_CUTOFF}"}

    to = profile.get("principalEmail")
    try:
        brief = service.build_brief(store, school_id, date, mode="live", now=now)
    except BriefInvalid as e:
        if send and to:  # never silent: tell the principal the plan could not be built
            send(to, f"AirDay {date:%a %d %b}: today's plan could not be built",
                 "We couldn't build today's plan. Check the official AQI before outdoor activities.",
                 "<p>We couldn't build today's plan. Check the official AQI before outdoor activities.</p>")
        log.error(json.dumps(base | {"valid": False, "problems": e.problems}))
        raise

    service.store_brief(store, school_id, brief)
    email = {"sent": False, "reason": "email not configured"}
    if send and to:
        email = mailer.send_daily(store, school_id, brief, to, send, dashboard_url)
    return base | {
        "valid": True,
        "worstBand": brief["worstBand"],
        "changes": sum(1 for a in brief["actions"] if a["change"] and a["kind"] != "note"),
        "ruleIds": sorted({r for a in brief["actions"] for r in a["ruleIds"]}),
        "escalated": [h["hour"] for h in brief["hours"] if h["escalated"]],
        "upstream": brief["upstream"],
        "email": email,
    }


def process_batch(store: Store, records: Iterable[dict], now: dt.datetime,
                  send: Callable[[str, str, str, str], str] | None, dashboard_url: str = "") -> dict:
    """SQS batch with partial failure reporting: only failed messages go back to the queue."""
    failures, results = [], []
    for r in records:
        try:
            results.append(run_job(store, json.loads(r["body"]), now, send, dashboard_url))
        except Exception as e:
            log.exception("job failed: %s", r.get("messageId"))
            failures.append({"itemIdentifier": r["messageId"]})
            results.append({"messageId": r.get("messageId"), "error": str(e)[:200]})
    return {"batchItemFailures": failures, "results": results}


def today(now: dt.datetime | None = None) -> dt.date:
    return (now or tu.now_ist()).date()
