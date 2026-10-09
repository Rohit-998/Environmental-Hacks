"""Builds briefs: fetches (or loads cached / fixture) data, runs the engine, validates, stores.

This is the only module that combines I/O with the engine. Handlers call into it. Every function is scoped to
one school (tenant). Upstream data is cached in a shared partition keyed by forecast grid cell or sensor, so a
city with 1,000 schools costs one forecast call, not 1,000.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import logging
import os
import time
import uuid
from typing import Any

from . import school as schoolmod
from . import sources
from . import timeutil as tu
from .brief import Official, to_brief
from .engine import Reading, build_plan, hourly_bands
from .rules import RuleSet, load
from .store import CACHE_PK, DEMO_SCHOOL, REGISTRY_PK, Store, school_pk
from .validator import assert_valid

log = logging.getLogger("airday")

FIXTURES = os.environ.get(
    "AIRDAY_FIXTURES", os.path.join(os.path.dirname(__file__), "..", "fixtures", "replay")
)
STATION_MAX_AGE_MIN = int(os.environ.get("STATION_MAX_AGE_MIN", "120"))
# The station band floors the rest of the day. Chosen by the backtest (backtest/report.md): CAMS reads far
# cleaner than Delhi stations in winter, and a 3-hour window missed most bad hours.
STATION_FLOOR_HOURS = int(os.environ.get("STATION_FLOOR_HOURS", "24"))
CACHE_TTL_S = int(os.environ.get("CACHE_TTL_S", "600"))
GRID_DEG = 0.4  # CAMS Global resolution


class SchoolNotFound(KeyError):
    pass


# ---------------------------------------------------------------- schools (tenants)

def grid_key(lat: float, lon: float) -> tuple[str, float, float]:
    """Snap to the CAMS 0.4° grid. Schools in the same cell share one forecast fetch."""
    glat, glon = round(round(lat / GRID_DEG) * GRID_DEG, 2), round(round(lon / GRID_DEG) * GRID_DEG, 2)
    return f"{glat:.2f}_{glon:.2f}", glat, glon


def get_profile(store: Store, school_id: str) -> dict:
    p = store.get(school_pk(school_id), "PROFILE")
    if p is None:
        if school_id != DEMO_SCHOOL:
            raise SchoolNotFound(school_id)
        p = dict(schoolmod.SAMPLE_PROFILE)
        save_profile(store, school_id, p)
    return p


def save_profile(store: Store, school_id: str, profile: dict) -> None:
    store.put(school_pk(school_id), "PROFILE", profile)
    g, _, _ = grid_key(profile["lat"], profile["lon"])
    store.put(REGISTRY_PK, f"SCHOOL#{school_id}", {"schoolId": school_id, "grid": g, "name": profile.get("name", "")})


def create_school(store: Store, profile: dict, owner: str) -> str:
    """New tenant. The owner (a Cognito user sub) is mapped to the school server-side."""
    school_id = uuid.uuid4().hex[:12]
    save_profile(store, school_id, dict(schoolmod.SAMPLE_PROFILE) | profile | {"owner": owner})
    store.put(f"USER#{owner}", "SCHOOL", {"schoolId": school_id})
    return school_id


def school_for_user(store: Store, sub: str) -> str | None:
    item = store.get(f"USER#{sub}", "SCHOOL")
    return item["schoolId"] if item else None


def list_schools(store: Store) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "SK"} for r in store.query_prefix(REGISTRY_PK, "SCHOOL#")]


def get_timetable(store: Store, school_id: str) -> list[dict]:
    rows = store.query_prefix(school_pk(school_id), "ACTIVITY#")
    if not rows:
        if school_id != DEMO_SCHOOL:
            return []
        parsed, _ = schoolmod.parse_timetable_csv(schoolmod.SAMPLE_CSV, "07:45", "14:00")
        rows = schoolmod.with_ids(parsed)
        replace_timetable(store, school_id, rows)
        return rows
    return [{k: v for k, v in r.items() if k != "SK"} for r in rows]


def replace_timetable(store: Store, school_id: str, rows: list[dict]) -> None:
    pk = school_pk(school_id)
    for old in store.query_prefix(pk, "ACTIVITY#"):
        store.delete(pk, old["SK"])
    for r in rows:
        store.put(pk, f"ACTIVITY#{r['id']}", r)


# ---------------------------------------------------------------- shared upstream cache

def _cached(store: Store, key: str, fetch, ttl: int = CACHE_TTL_S) -> tuple[Any, str]:
    """Returns (data, status). status: fresh | cached | stale-cache from HH:MM. Raises UpstreamError if nothing."""
    item = store.get(CACHE_PK, key)
    now = time.time()
    if item and now - item["fetchedAt"] < ttl:
        return item["raw"], "cached"
    try:
        raw = fetch()
        store.put(CACHE_PK, key, {"raw": raw, "fetchedAt": now, "expiresAt": int(now) + 2 * 86400})
        return raw, "fresh"
    except sources.UpstreamError:
        if item:
            log.warning("upstream failed, using cache for %s", key)
            fetched = dt.datetime.fromtimestamp(item["fetchedAt"], tu.IST).strftime("%H:%M")
            return item["raw"], f"stale-cache from {fetched}"
        raise


def live_forecast(store: Store, profile: dict, date: dt.date, days: int = 3) -> tuple[dict[str, list[Reading]], str]:
    g, glat, glon = grid_key(profile["lat"], profile["lon"])
    start, end = date.isoformat(), (date + dt.timedelta(days=days - 1)).isoformat()
    raw, status = _cached(store, f"openmeteo#{g}#{start}",
                          lambda: sources.fetch_open_meteo(glat, glon, start, end))
    return sources.parse_open_meteo(raw), status


def warm_forecast(store: Store, lat: float, lon: float, date: dt.date) -> str:
    """Planner helper: fetch one grid cell's forecast into the shared cache."""
    _, status = live_forecast(store, {"lat": lat, "lon": lon}, date)
    return status


def live_station(store: Store, profile: dict, date: dt.date) -> tuple[list[Reading], str]:
    key = os.environ.get("OPENAQ_API_KEY")
    sensors = profile.get("openaqSensors") or {}
    if not key or not (sensors.get("pm25") or sensors.get("pm10")):
        return [], "not configured"
    out = {}
    for name in ("pm25", "pm10"):
        sid = sensors.get(name)
        if not sid:
            out[name] = {}
            continue
        raw, _ = _cached(store, f"openaq#{sid}#{date.isoformat()}",
                         lambda sid=sid: sources.fetch_openaq_hours(int(sid), date.isoformat(), key))
        out[name] = sources.parse_openaq_hours(raw)
    return sources.merge_station(out["pm25"], out["pm10"]), "ok"


def live_official(store: Store, profile: dict) -> tuple[Official, str]:
    key = os.environ.get("DATA_GOV_API_KEY")
    if not key:
        return Official(grap_override=profile.get("grapOverride")), "not configured"
    raw, status = _cached(store, "datagov#Delhi#latest", lambda: sources.fetch_data_gov(key), ttl=1800)
    stations = sources.parse_data_gov(raw)
    from .aqi import city_average

    mine = stations.get(profile.get("cpcbStation") or "", {})
    return Official(
        station_aqi=mine.get("aqi"),
        station_name=profile.get("cpcbStation"),
        station_as_of=mine.get("asOf"),
        city_aqi=city_average([s.get("aqi") for s in stations.values()]),
        city_source="live",
        city_as_of=mine.get("asOf"),
        grap_override=profile.get("grapOverride"),
    ), status


def latest_fresh_station_hour(station: list[Reading], now: dt.datetime) -> int | None:
    """Hour of the latest station reading whose hour ended no more than STATION_MAX_AGE_MIN ago."""
    hours = [r.hour for r in station if r.pm25 is not None or r.pm10 is not None]
    if not hours:
        return None
    h = max(hours)
    end_of_hour = now.replace(hour=h, minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    age_min = (now - end_of_hour).total_seconds() / 60
    return h if age_min <= STATION_MAX_AGE_MIN else None


# ---------------------------------------------------------------- replay fixtures

def replay_dates() -> list[str]:
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(FIXTURES, "*.json")))


def load_fixture(date: str) -> dict:
    if date not in replay_dates():
        raise KeyError(f"no replay fixture for {date}")
    with open(os.path.join(FIXTURES, f"{date}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _fixture_station(fx: dict) -> list[Reading]:
    oaq = fx.get("openaq") or {}
    return sources.merge_station({int(k): v for k, v in (oaq.get("pm25") or {}).items()},
                                 {int(k): v for k, v in (oaq.get("pm10") or {}).items()})


def load_fixture_containing(date: dt.date) -> dict:
    """Replay fixtures hold the replay date plus 2 more days, so chat can plan ahead."""
    for d in replay_dates():
        start = dt.date.fromisoformat(d)
        if start <= date <= start + dt.timedelta(days=2):
            return load_fixture(d)
    raise KeyError(f"no replay data covers {date}")


# ---------------------------------------------------------------- build

def build_brief(
    store: Store,
    school_id: str,
    date: dt.date,
    mode: str = "live",
    now: dt.datetime | None = None,
    rs: RuleSet | None = None,
) -> dict:
    """Build and validate a brief. Live mode reads upstream through the shared cache; replay mode uses the
    frozen fixture "as of 06:00" on that date. Raises BriefInvalid or SchoolNotFound."""
    rs = rs or load()
    profile = get_profile(store, school_id)
    rows = get_timetable(store, school_id)
    acts = schoolmod.activities_for(rows, date)
    upstream: dict[str, str] = {}

    if mode == "replay":
        fx = load_fixture(date.isoformat())
        forecast = sources.parse_open_meteo(fx["openMeteo"]).get(date.isoformat(), [])
        # Replay is "as of 06:00": only station readings from hours before 06:00 are known.
        station = [r for r in _fixture_station(fx) if r.hour < 6]
        now = dt.datetime.combine(date, dt.time(6, 0), tu.IST)
        off = fx.get("official", {})
        official = Official(city_aqi=off.get("cityAqi"), city_source="bulletin", city_as_of=off.get("cityAsOf"))
        upstream = {"forecast": "fixture", "station": "fixture" if station else "none", "official": "bulletin fixture"}
    else:
        now = now or tu.now_ist()
        try:
            days, status = live_forecast(store, profile, date)
            forecast = days.get(date.isoformat(), [])
            upstream["forecast"] = status
        except sources.UpstreamError as e:
            log.error("forecast unavailable: %s", e)
            forecast, upstream["forecast"] = [], "unavailable"
        try:
            station, upstream["station"] = live_station(store, profile, date)
        except sources.UpstreamError:
            station, upstream["station"] = [], "unavailable"
        try:
            official, upstream["official"] = live_official(store, profile)
        except sources.UpstreamError as e:
            log.warning("official AQI unavailable: %s", e)
            official, upstream["official"] = Official(grap_override=profile.get("grapOverride")), "unavailable"

    st_hour = latest_fresh_station_hour(station, now) if station and now.date() == date else None
    bands = hourly_bands(rs, forecast, station, st_hour, escalation_hours=STATION_FLOOR_HOURS)
    plan = build_plan(rs, date.isoformat(), profile["start"], profile["end"], acts, bands)
    brief = to_brief(rs, plan, date, official, mode=mode, upstream=upstream,
                     school_name=profile.get("name", ""), labels={a.id: a.label for a in acts},
                     generated_at=now.isoformat(timespec="seconds"))
    brief["schoolId"] = school_id
    brief["schoolDay"] = schoolmod.is_school_day(profile, date)
    if upstream.get("forecast") == "unavailable":
        brief["headline"] = "Forecast unavailable today. Check the official AQI before outdoor activities."
    assert_valid(rs, brief, [a.id for a in acts])
    return brief


def store_brief(store: Store, school_id: str, brief: dict) -> None:
    key = ("REPLAY#" if brief["mode"] == "replay" else "BRIEF#") + brief["date"]
    store.put(school_pk(school_id), key, brief)


def get_stored(store: Store, school_id: str, date: str, mode: str = "live") -> dict | None:
    return store.get(school_pk(school_id), ("REPLAY#" if mode == "replay" else "BRIEF#") + date)


def diff(old: dict | None, new: dict) -> list[dict]:
    """Actions whose rule IDs changed since the stored brief."""
    if not old:
        return []
    before = {(a["kind"], a.get("activityId"), tuple(a["hours"])): a["ruleIds"] for a in old["actions"]}
    out = []
    for a in new["actions"]:
        k = (a["kind"], a.get("activityId"), tuple(a["hours"]))
        if k in before and before[k] != a["ruleIds"]:
            out.append({"text": a["text"], "was": before[k], "now": a["ruleIds"]})
    return out


def evaluate(store: Store, school_id: str, typ: str, date: dt.date, start: str, end: str, mode: str = "live",
             rs: RuleSet | None = None) -> dict:
    """Deterministic activity check (the "Check an activity" form and the chat tool)."""
    rs = rs or load()
    from .engine import activity_band

    if typ not in ("assembly", "recess", "pe"):
        raise ValueError("type must be assembly, recess or pe")
    s, e = tu.parse_hhmm(start), tu.parse_hhmm(end)
    if s >= e:
        raise ValueError("start must be before end")
    # Same bands as the brief: the station floor applies to the day the readings are from (the replay day as of
    # 06:00, or today live). Future days have no station data yet, so they use the forecast alone.
    station: list[Reading] = []
    now: dt.datetime | None = None
    if mode == "replay":
        fx = load_fixture_containing(date)
        forecast = sources.parse_open_meteo(fx["openMeteo"]).get(date.isoformat(), [])
        if fx["date"] == date.isoformat():
            station = [r for r in _fixture_station(fx) if r.hour < 6]
            now = dt.datetime.combine(date, dt.time(6, 0), tu.IST)
    else:
        profile = get_profile(store, school_id)
        today = tu.now_ist().date()
        days, _ = live_forecast(store, profile, today)
        forecast = days.get(date.isoformat(), [])
        if date == today:
            try:
                station, _ = live_station(store, profile, date)
            except sources.UpstreamError:
                station = []
            now = tu.now_ist()
    st_hour = latest_fresh_station_hour(station, now) if station and now else None
    bands = hourly_bands(rs, forecast, station, st_hour, escalation_hours=STATION_FLOOR_HOURS)
    hrs = tu.hours_overlapped(s, e)
    band = activity_band(rs, bands, hrs)
    rule = rs.rule(band, typ)
    return {
        "type": typ, "date": date.isoformat(), "start": start, "end": end,
        "band": band, "bandName": rs.name(band), "ruleId": rule.id, "change": rule.change,
        "text": rule.en.format(label=typ.upper() if typ == "pe" else typ.capitalize(), start=start, end=end),
        "hours": [{"hour": h, "pm25": bands[h].pm25 if h in bands else None,
                   "band": bands[h].band if h in bands else "unknown"} for h in hrs],
    }
