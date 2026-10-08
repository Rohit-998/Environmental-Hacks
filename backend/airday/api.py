"""HTTP API router shared by the Lambda handler and the local dev server.

route(method, path, query, body, headers, store) -> (status, json-able body)
"""
from __future__ import annotations

import datetime as dt
import hmac
import json
import logging
import os
from typing import Any, Callable

from . import mailer, service
from . import school as schoolmod
from . import timeutil as tu
from .rules import load
from .store import Store, school_pk
from .validator import BriefInvalid

log = logging.getLogger("airday")

Response = tuple[int, Any]


class HttpError(Exception):
    def __init__(self, status: int, message: str, **extra: Any):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


def admin_key() -> str | None:
    return os.environ.get("ADMIN_KEY") or None


def require_admin(headers: dict[str, str]) -> None:
    expected = admin_key()
    got = headers.get("x-admin-key", "")
    if not expected:
        raise HttpError(503, "admin key is not configured on the server")
    if not hmac.compare_digest(got.encode(), expected.encode()):
        raise HttpError(401, "admin key missing or wrong")


def _date(q: dict[str, str], name: str = "date", default: dt.date | None = None) -> dt.date:
    raw = q.get(name)
    if not raw:
        if default is None:
            raise HttpError(400, f"{name} is required (YYYY-MM-DD)")
        return default
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise HttpError(400, f"{name} must be YYYY-MM-DD")


def _json(body: str | None) -> Any:
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise HttpError(400, "body is not valid JSON")


# ---------------------------------------------------------------- handlers

def get_school(store, q, body, headers) -> Response:
    return 200, schoolmod.public_profile(service.get_profile(store))


def put_school(store, q, body, headers) -> Response:
    require_admin(headers)
    current = service.get_profile(store)
    patch = _json(body)
    allowed = set(schoolmod.SAMPLE_PROFILE)
    unknown = sorted(set(patch) - allowed)
    if unknown:
        raise HttpError(400, f"unknown fields: {', '.join(unknown)}")
    new = current | patch
    if new.get("grapOverride") and not new["grapOverride"].get("expiresAt"):
        today = tu.now_ist().date()
        new["grapOverride"] = new["grapOverride"] | {
            "setAt": today.isoformat(), "expiresAt": (today + dt.timedelta(days=3)).isoformat()}
    errs = schoolmod.validate_profile(new)
    if errs:
        raise HttpError(400, "invalid profile", errors=errs)
    store.put(school_pk(), "PROFILE", new)
    return 200, schoolmod.public_profile(new)


def get_activities(store, q, body, headers) -> Response:
    return 200, {"activities": service.get_timetable(store)}


def put_activities(store, q, body, headers) -> Response:
    require_admin(headers)
    p = service.get_profile(store)
    ctype = headers.get("content-type", "")
    if "json" in ctype:
        data = _json(body)
        rows = data.get("activities") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise HttpError(400, "body must be {activities: [...]}")
        errors = schoolmod.validate_rows(rows, p["start"], p["end"])
        if errors:
            return 400, {"error": "some rows are invalid", "rowErrors": errors}
        parsed = rows
    else:
        parsed, errors = schoolmod.parse_timetable_csv(body or "", p["start"], p["end"])
        if errors:
            return 400, {"error": "some rows are invalid", "rowErrors": errors, "validRows": len(parsed)}
    rows = schoolmod.with_ids(parsed)
    service.replace_timetable(store, rows)
    return 200, {"activities": rows}


def get_sample_timetable(store, q, body, headers) -> Response:
    return 200, {"csv": schoolmod.SAMPLE_CSV}


def get_brief(store, q, body, headers) -> Response:
    date = _date(q, default=tu.now_ist().date())
    b = service.get_stored(store, date.isoformat(), "live")
    if b is None:
        raise HttpError(404, f"no brief stored for {date}")
    return 200, b


def get_brief_live(store, q, body, headers) -> Response:
    date = _date(q, default=tu.now_ist().date())
    try:
        b = service.build_brief(store, date, mode="live")
    except BriefInvalid as e:
        raise HttpError(500, "brief failed validation", problems=e.problems)
    stored = service.get_stored(store, date.isoformat(), "live")
    b["changedSinceEmail"] = service.diff(stored, b)
    b["emailedAt"] = (stored or {}).get("generatedAt")
    return 200, b


def post_regenerate(store, q, body, headers) -> Response:
    require_admin(headers)
    date = _date(q, default=tu.now_ist().date())
    b = service.build_brief(store, date, mode="live")
    service.store_brief(store, b)
    if q.get("resend") == "true":
        _email_now(store, b)
    return 200, b


def get_replay_dates(store, q, body, headers) -> Response:
    return 200, {"dates": service.replay_dates()}


def get_replay(store, q, body, headers) -> Response:
    date = _date(q)
    try:
        b = service.build_brief(store, date, mode="replay")
    except KeyError as e:
        raise HttpError(404, str(e))
    service.store_brief(store, b)
    return 200, b


def post_replay_email(store, q, body, headers) -> Response:
    require_admin(headers)
    date = _date(q)
    try:
        b = service.build_brief(store, date, mode="replay")
    except KeyError as e:
        raise HttpError(404, str(e))
    return 200, {"sent": True, "messageId": _email_now(store, b)}


def _email_now(store: Store, b: dict) -> str:
    send = mailer.configured_sender()
    to = service.get_profile(store).get("principalEmail")
    if not send:
        raise HttpError(503, "email is not configured (SES_SENDER)")
    if not to:
        raise HttpError(400, "principal email is not set")
    return mailer.send_once_more(b, to, send, os.environ.get("DASHBOARD_URL", ""))


def get_evaluate(store, q, body, headers) -> Response:
    date = _date(q)
    mode = q.get("mode", "live")
    try:
        return 200, service.evaluate(store, q.get("type", ""), date, q.get("start", ""), q.get("end", ""), mode=mode)
    except (ValueError, KeyError) as e:
        raise HttpError(400, str(e))


def get_rules(store, q, body, headers) -> Response:
    rs = load()
    return 200, {"version": rs.version, "bands": {"order": rs.order, "names": rs.names,
                 "pm25Upper": rs.pm25_upper, "pm10Upper": rs.pm10_upper},
                 "rules": [r.__dict__ for r in rs.rules.values()]}


def get_health(store, q, body, headers) -> Response:
    return 200, {"ok": True, "time": tu.now_ist().isoformat(timespec="seconds")}


ROUTES: dict[tuple[str, str], Callable[..., Response]] = {
    ("GET", "/health"): get_health,
    ("GET", "/school"): get_school,
    ("PUT", "/school"): put_school,
    ("GET", "/activities"): get_activities,
    ("PUT", "/activities"): put_activities,
    ("GET", "/activities/sample"): get_sample_timetable,
    ("GET", "/brief"): get_brief,
    ("GET", "/brief/live"): get_brief_live,
    ("POST", "/brief/regenerate"): post_regenerate,
    ("GET", "/replay/dates"): get_replay_dates,
    ("GET", "/replay"): get_replay,
    ("POST", "/replay/email"): post_replay_email,
    ("GET", "/evaluate"): get_evaluate,
    ("GET", "/rules"): get_rules,
}


def route(method: str, path: str, query: dict[str, str], body: str | None,
          headers: dict[str, str], store: Store, extra: dict | None = None) -> Response:
    routes = ROUTES | (extra or {})
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    path = "/" + path.strip("/")
    fn = routes.get((method.upper(), path))
    if fn is None:
        if any(p == path for _, p in routes):
            return 405, {"error": "method not allowed"}
        return 404, {"error": "not found"}
    try:
        return fn(store, query or {}, body, headers)
    except HttpError as e:
        return e.status, {"error": e.message, **e.extra}
    except BriefInvalid as e:
        log.error("brief invalid: %s", e.problems)
        return 500, {"error": "brief failed validation", "problems": e.problems}
    except Exception:
        log.exception("unhandled error on %s %s", method, path)
        return 500, {"error": "internal error"}
