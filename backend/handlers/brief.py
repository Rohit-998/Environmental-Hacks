"""Scheduled Lambda: builds today's brief at 06:00 IST and emails the principal at most once.

Invoked by EventBridge Scheduler. Raising makes the Scheduler retry (configured: 2 retries).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os

from airday import mailer, service
from airday import school as schoolmod
from airday import timeutil as tu
from airday.store import default_store
from airday.validator import BriefInvalid

log = logging.getLogger()
log.setLevel(logging.INFO)

SEND_CUTOFF = os.environ.get("SEND_CUTOFF", "07:30")


def _log(**fields) -> None:
    """One structured line per run. This is the line shown in the demo video."""
    print(json.dumps({"event": "daily_brief", **fields}, ensure_ascii=False))


def handler(event, context):
    store = default_store()
    now = tu.now_ist()
    date = dt.date.fromisoformat(event["date"]) if isinstance(event, dict) and event.get("date") else now.date()
    profile = service.get_profile(store)

    if not schoolmod.is_school_day(profile, date):
        _log(date=date.isoformat(), skipped=True, reason="not a school day")
        return {"skipped": True}

    if now.date() == date and now.strftime("%H:%M") > SEND_CUTOFF:
        _log(date=date.isoformat(), skipped=True, reason=f"after send cutoff {SEND_CUTOFF}")
        return {"skipped": True}

    to = profile.get("principalEmail")
    send = mailer.configured_sender()
    dashboard = os.environ.get("DASHBOARD_URL", "")

    try:
        brief = service.build_brief(store, date, mode="live", now=now)
    except BriefInvalid as e:
        _log(date=date.isoformat(), valid=False, problems=e.problems)
        if send and to:
            # Never silent: tell the principal the plan could not be built.
            send(to, f"AirDay {date:%a %d %b}: today's plan could not be built",
                 "We couldn't build today's plan. Check the official AQI before outdoor activities.",
                 "<p>We couldn't build today's plan. Check the official AQI before outdoor activities.</p>")
        raise

    service.store_brief(store, brief)
    result = {"sent": False, "reason": "email not configured"}
    if send and to:
        result = mailer.send_daily(store, brief, to, send, dashboard)

    _log(
        date=date.isoformat(),
        valid=True,
        worstBand=brief["worstBand"],
        bands={h["hour"]: h["band"] for h in brief["hours"] if 7 <= h["hour"] <= 14},
        ruleIds=sorted({r for a in brief["actions"] for r in a["ruleIds"]}),
        escalated=[h["hour"] for h in brief["hours"] if h["escalated"]],
        upstream=brief["upstream"],
        email=result,
    )
    return {"date": date.isoformat(), "email": result}
