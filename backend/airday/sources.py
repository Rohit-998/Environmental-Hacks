"""Upstream data sources: Open-Meteo (forecast), OpenAQ (station hourly), data.gov.in (official AQI).

Standard library only, so the Lambda package stays small. Every call has a timeout and one retry.
Parsers are separate from fetchers so they can be tested on fixtures.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import aqi as aqimod
from . import timeutil as tu
from .engine import Reading

TIMEOUT_S = 5
OPEN_METEO_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPENAQ = "https://api.openaq.org/v3"
DATA_GOV_AQI = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"


class UpstreamError(Exception):
    pass


def _get_json(url: str, headers: dict[str, str] | None = None, retries: int = 1) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "AirDay/0.1", **(headers or {})})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            if attempt < retries:
                time.sleep(0.5)
    raise UpstreamError(f"{url.split('?')[0]}: {last}")


# ---------------------------------------------------------------- Open-Meteo

def open_meteo_url(lat: float, lon: float, start: str, end: str) -> str:
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "hourly": "pm2_5,pm10",
        "timezone": "Asia/Kolkata", "start_date": start, "end_date": end,
    })
    return f"{OPEN_METEO_AQ}?{q}"


def fetch_open_meteo(lat: float, lon: float, start: str, end: str) -> dict:
    return _get_json(open_meteo_url(lat, lon, start, end))


def parse_open_meteo(raw: dict) -> dict[str, list[Reading]]:
    """{date: [Reading per hour]} from an Open-Meteo hourly response (times already in IST)."""
    h = raw.get("hourly") or {}
    out: dict[str, list[Reading]] = {}
    for t, p25, p10 in zip(h.get("time", []), h.get("pm2_5", []), h.get("pm10", []), strict=True):
        day, hhmm = t.split("T")
        out.setdefault(day, []).append(Reading(int(hhmm[:2]), p25, p10))
    return out


def geocode(name: str, count: int = 5) -> list[dict]:
    q = urllib.parse.urlencode({"name": name, "count": count, "country": "IN", "language": "en"})
    raw = _get_json(f"{OPEN_METEO_GEO}?{q}")
    return [{
        "name": r.get("name"), "admin1": r.get("admin1"), "admin2": r.get("admin2"),
        "lat": r.get("latitude"), "lon": r.get("longitude"),
    } for r in raw.get("results") or []]


# ---------------------------------------------------------------- OpenAQ v3

def fetch_openaq_hours(sensor_id: int, date: str, api_key: str) -> dict:
    """Hourly averages for one sensor for one IST date (UTC window 18:30 the day before to 18:30)."""
    q = urllib.parse.urlencode({
        "datetime_from": f"{_prev(date)}T18:30:00Z",
        "datetime_to": f"{date}T18:30:00Z",
        "limit": 48,
    })
    return _get_json(f"{OPENAQ}/sensors/{sensor_id}/hours?{q}", headers={"X-API-Key": api_key})


def _prev(date: str) -> str:
    import datetime as dt
    return (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat()


def parse_openaq_hours(raw: dict) -> dict[int, float]:
    """{IST hour: value}. An hourly average is assigned to the hour it starts in."""
    out: dict[int, float] = {}
    for r in raw.get("results") or []:
        period = r.get("period") or {}
        start = (period.get("datetimeFrom") or {}).get("utc")
        if start is None or r.get("value") is None:
            continue
        out[tu.to_ist(start).hour] = float(r["value"])
    return out


def merge_station(pm25: dict[int, float], pm10: dict[int, float]) -> list[Reading]:
    hours = sorted(set(pm25) | set(pm10))
    return [Reading(h, pm25.get(h), pm10.get(h)) for h in hours]


# ---------------------------------------------------------------- data.gov.in (CPCB real-time)

def fetch_data_gov(api_key: str, city: str = "Delhi", limit: int = 1000) -> dict:
    q = urllib.parse.urlencode({
        "api-key": api_key, "format": "json", "limit": limit, "filters[city]": city,
    })
    return _get_json(f"{DATA_GOV_AQI}?{q}")


_POLLUTANT_KEYS = {"PM2.5": "PM2.5", "PM10": "PM10", "NO2": "NO2", "SO2": "SO2",
                   "CO": "CO", "OZONE": "OZONE", "NH3": "NH3"}


def parse_data_gov(raw: dict) -> dict[str, dict[str, Any]]:
    """{station: {"aqi": int|None, "asOf": str, "subIndices": {...}}}.

    The feed has one row per station per pollutant. Field meanings must be confirmed (PRD §16);
    this assumes `avg_value` is the pollutant's sub-index on the 24-hour basis.
    """
    stations: dict[str, dict[str, Any]] = {}
    for r in raw.get("records") or []:
        st = r.get("station")
        pid = _POLLUTANT_KEYS.get(str(r.get("pollutant_id", "")).upper())
        if not st or not pid:
            continue
        s = stations.setdefault(st, {"subIndices": {}, "asOf": r.get("last_update")})
        try:
            s["subIndices"][pid] = float(r.get("avg_value"))
        except (TypeError, ValueError):
            s["subIndices"][pid] = None
    for s in stations.values():
        s["aqi"] = aqimod.station_aqi(s["subIndices"])
    return stations
