"""HTTP API router shared by the Lambda handler and the local dev server.

route(method, path, query, body, headers, store, claims=None) -> (status, json-able body)

Two route trees with the same handlers:
  /...     public demo school (read-only; writes need the demo admin key)
  /me/...  the signed-in user's own school (JWT verified by API Gateway, claims passed in)
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from collections.abc import Callable
from typing import Any

from . import mailer, service, verify
from . import school as schoolmod
from . import timeutil as tu
from .auth import Principal, demo_principal, user_principal
from .rules import load
from .store import Store
from .validator import BriefInvalid

log = logging.getLogger("airday")

Response = tuple[int, Any]
Handler = Callable[[Store, Principal, dict, str | None, dict], Response]


class HttpError(Exception):
    def __init__(self, status: int, message: str, **extra: Any):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


def require_write(p: Principal) -> None:
    if not p.can_write:
        raise HttpError(401, "sign in, or add the demo admin key, to make changes")


def require_school(p: Principal) -> str:
    if not p.school_id:
        raise HttpError(404, "no school yet: create one with POST /me/school")
    return p.school_id


def _date(q: dict[str, str], name: str = "date", default: dt.date | None = None) -> dt.date:
    raw = q.get(name)
    if not raw:
        if default is None:
            raise HttpError(400, f"{name} is required (YYYY-MM-DD)")
        return default
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise HttpError(400, f"{name} must be YYYY-MM-DD") from None


def _json(body: str | None) -> Any:
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise HttpError(400, "body is not valid JSON") from None


EDITABLE = set(schoolmod.SAMPLE_PROFILE)


def _apply_patch(current: dict, patch: dict) -> dict:
    unknown = sorted(set(patch) - EDITABLE)
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
    return new


# ---------------------------------------------------------------- handlers

def get_me(store, p, q, body, headers) -> Response:
    return 200, p.public()


def create_school(store, p, q, body, headers) -> Response:
    if p.kind != "user":
        raise HttpError(401, "sign in to create a school")
    if p.school_id:
        raise HttpError(409, "you already have a school", schoolId=p.school_id)
    patch = _json(body)
    profile = _apply_patch(dict(schoolmod.SAMPLE_PROFILE), patch)
    _verify_if_changed({}, profile)
    school_id = service.create_school(store, profile, owner=p.sub)
    return 201, {"schoolId": school_id, **_public(profile)}


def _verify_if_changed(old: dict, new: dict) -> None:
    """SES sandbox: a new principal email gets a verification link before the 06:00 plan can reach it."""
    email = new.get("principalEmail") or ""
    if not email:
        new["emailStatus"] = None
    elif email != old.get("principalEmail") or not old.get("emailStatus"):
        new["emailStatus"] = verify.verifier().request(email)


def _public(profile: dict) -> dict:
    return schoolmod.public_profile(profile) | {"emailStatus": profile.get("emailStatus")}


def get_school(store, p, q, body, headers) -> Response:
    sid = require_school(p)
    profile = service.get_profile(store, sid)
    if profile.get("principalEmail") and profile.get("emailStatus") == verify.PENDING:
        status = verify.verifier().status(profile["principalEmail"])
        if status != verify.PENDING:  # the principal clicked the link (or it expired): remember the outcome
            profile["emailStatus"] = status
            service.save_profile(store, sid, profile)
    return 200, _public(profile)


def put_school(store, p, q, body, headers) -> Response:
    require_write(p)
    sid = require_school(p)
    old = service.get_profile(store, sid)
    new = _apply_patch(old, _json(body))
    _verify_if_changed(old, new)
    service.save_profile(store, sid, new)
    return 200, _public(new)


def post_resend_verification(store, p, q, body, headers) -> Response:
    require_write(p)
    sid = require_school(p)
    profile = service.get_profile(store, sid)
    if not profile.get("principalEmail"):
        raise HttpError(400, "set a principal email first")
    profile["emailStatus"] = verify.verifier().request(profile["principalEmail"])
    service.save_profile(store, sid, profile)
    return 200, _public(profile)


def get_activities(store, p, q, body, headers) -> Response:
    return 200, {"activities": service.get_timetable(store, require_school(p))}


def put_activities(store, p, q, body, headers) -> Response:
    require_write(p)
    sid = require_school(p)
    prof = service.get_profile(store, sid)
    if "json" in headers.get("content-type", ""):
        data = _json(body)
        rows = data.get("activities") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise HttpError(400, "body must be {activities: [...]}")
        errors = schoolmod.validate_rows(rows, prof["start"], prof["end"])
        if errors:
            return 400, {"error": "some rows are invalid", "rowErrors": errors}
        parsed = rows
    else:
        parsed, errors = schoolmod.parse_timetable_csv(body or "", prof["start"], prof["end"])
        if errors:
            return 400, {"error": "some rows are invalid", "rowErrors": errors, "validRows": len(parsed)}
    rows = schoolmod.with_ids(parsed)
    service.replace_timetable(store, sid, rows)
    return 200, {"activities": rows}


def get_sample_timetable(store, p, q, body, headers) -> Response:
    return 200, {"csv": schoolmod.SAMPLE_CSV}


def get_brief(store, p, q, body, headers) -> Response:
    sid = require_school(p)
    date = _date(q, default=tu.now_ist().date())
    b = service.get_stored(store, sid, date.isoformat(), "live")
    if b is None:
        raise HttpError(404, f"no brief stored for {date}")
    return 200, b


def get_brief_live(store, p, q, body, headers) -> Response:
    sid = require_school(p)
    date = _date(q, default=tu.now_ist().date())
    b = service.build_brief(store, sid, date, mode="live")
    stored = service.get_stored(store, sid, date.isoformat(), "live")
    b["changedSinceEmail"] = service.diff(stored, b)
    b["emailedAt"] = (stored or {}).get("generatedAt")
    return 200, b


def post_regenerate(store, p, q, body, headers) -> Response:
    require_write(p)
    sid = require_school(p)
    date = _date(q, default=tu.now_ist().date())
    b = service.build_brief(store, sid, date, mode="live")
    service.store_brief(store, sid, b)
    if q.get("resend") == "true":
        _email_now(store, sid, b)
    return 200, b


def get_replay_dates(store, p, q, body, headers) -> Response:
    return 200, {"dates": service.replay_dates()}


def get_replay(store, p, q, body, headers) -> Response:
    sid = require_school(p)
    date = _date(q)
    try:
        b = service.build_brief(store, sid, date, mode="replay")
    except KeyError as e:
        raise HttpError(404, str(e).strip("'")) from None
    service.store_brief(store, sid, b)
    return 200, b


def post_replay_email(store, p, q, body, headers) -> Response:
    require_write(p)
    sid = require_school(p)
    date = _date(q)
    try:
        b = service.build_brief(store, sid, date, mode="replay")
    except KeyError as e:
        raise HttpError(404, str(e).strip("'")) from None
    return 200, {"sent": True, "messageId": _email_now(store, sid, b)}


def _email_now(store: Store, school_id: str, b: dict) -> str:
    send = mailer.configured_sender()
    to = service.get_profile(store, school_id).get("principalEmail")
    if not send:
        raise HttpError(503, "email is not configured (SES_SENDER)")
    if not to:
        raise HttpError(400, "principal email is not set")
    return mailer.send_once_more(b, to, send, os.environ.get("DASHBOARD_URL", ""))


def get_evaluate(store, p, q, body, headers) -> Response:
    sid = require_school(p)
    date = _date(q)
    try:
        return 200, service.evaluate(store, sid, q.get("type", ""), date, q.get("start", ""), q.get("end", ""),
                                     mode=q.get("mode", "live"))
    except (ValueError, KeyError) as e:
        raise HttpError(400, str(e).strip("'")) from None


def get_rules(store, p, q, body, headers) -> Response:
    rs = load()
    return 200, {"version": rs.version, "bands": {"order": rs.order, "names": rs.names,
                 "pm25Upper": rs.pm25_upper, "pm10Upper": rs.pm10_upper},
                 "rules": [r.__dict__ for r in rs.rules.values()]}


def get_health(store, p, q, body, headers) -> Response:
    return 200, {"ok": True, "time": tu.now_ist().isoformat(timespec="seconds")}


# Routes available under both / (demo) and /me (signed-in school).
TENANT_ROUTES: dict[tuple[str, str], Handler] = {
    ("GET", "/school"): get_school,
    ("PUT", "/school"): put_school,
    ("POST", "/school/verify-email"): post_resend_verification,
    ("GET", "/activities"): get_activities,
    ("PUT", "/activities"): put_activities,
    ("GET", "/brief"): get_brief,
    ("GET", "/brief/live"): get_brief_live,
    ("POST", "/brief/regenerate"): post_regenerate,
    ("GET", "/replay"): get_replay,
    ("POST", "/replay/email"): post_replay_email,
    ("GET", "/evaluate"): get_evaluate,
}
PUBLIC_ROUTES: dict[tuple[str, str], Handler] = {
    ("GET", "/health"): get_health,
    ("GET", "/rules"): get_rules,
    ("GET", "/replay/dates"): get_replay_dates,
    ("GET", "/activities/sample"): get_sample_timetable,
}
ME_ONLY: dict[tuple[str, str], Handler] = {
    ("GET", "/me"): get_me,
    ("POST", "/me/school"): create_school,
}


def build_routes(extra_tenant: dict | None = None) -> dict[tuple[str, str], Handler]:
    tenant = TENANT_ROUTES | (extra_tenant or {})
    routes = dict(PUBLIC_ROUTES) | ME_ONLY
    for (m, path), fn in tenant.items():
        routes[(m, path)] = fn
        routes[(m, "/me" + path)] = fn
    return routes


def route(method: str, path: str, query: dict[str, str], body: str | None, headers: dict[str, str],
          store: Store, extra: dict | None = None, claims: dict | None = None) -> Response:
    routes = build_routes(extra)
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    path = "/" + path.strip("/")
    if method.upper() == "OPTIONS":
        # CORS preflight. The catch-all ANY route forwards it here; API Gateway adds the CORS headers,
        # and browsers need a 2xx status.
        return 204, None
    fn = routes.get((method.upper(), path))
    if fn is None:
        if any(p == path for _, p in routes):
            return 405, {"error": "method not allowed"}
        return 404, {"error": "not found"}
    try:
        if path == "/me" or path.startswith("/me/"):
            if not claims:
                return 401, {"error": "sign in required"}
            principal = user_principal(store, claims)
        else:
            principal = demo_principal(headers)
        return fn(store, principal, query or {}, body, headers)
    except HttpError as e:
        return e.status, {"error": e.message, **e.extra}
    except service.SchoolNotFound:
        return 404, {"error": "school not found"}
    except BriefInvalid as e:
        log.error("brief invalid: %s", e.problems)
        return 500, {"error": "brief failed validation", "problems": e.problems}
    except PermissionError as e:
        return 401, {"error": str(e)}
    except Exception:
        log.exception("unhandled error on %s %s", method, path)
        return 500, {"error": "internal error"}
