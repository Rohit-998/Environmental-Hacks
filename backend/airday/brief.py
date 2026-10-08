"""Turns an engine Plan plus official-AQI context into the brief JSON (contracts/brief.schema.json)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from . import aqi as aqimod
from . import timeutil as tu
from .engine import Plan
from .rules import UNKNOWN, RuleSet

SCHEMA_VERSION = 1


@dataclass
class Official:
    """Official AQI context. Display only."""
    station_aqi: int | None = None
    station_name: str | None = None
    station_as_of: str | None = None  # "HH:MM" or ISO
    city_aqi: int | None = None
    city_source: str = "live"  # live | bulletin
    city_as_of: str | None = None
    grap_override: dict | None = None  # {"stage": "III", "setAt": iso, "expiresAt": iso}


def grap_info(official: Official, today: dt.date) -> dict[str, Any]:
    ov = official.grap_override
    if ov and ov.get("stage") and ov.get("expiresAt", "") >= today.isoformat():
        return {"stage": ov["stage"], "kind": "official",
                "label": f"GRAP Stage {ov['stage']} (official, set by admin)"}
    stage = aqimod.grap_stage(official.city_aqi)
    if stage is None:
        return {"stage": None, "kind": "indicative",
                "label": "No GRAP stage indicated" if official.city_aqi is not None
                else "GRAP stage unavailable"}
    return {"stage": stage, "kind": "indicative",
            "label": f"Indicative GRAP Stage {stage} (from Delhi average AQI, not a CAQM order)"}


def subject_line(date: dt.date, plan: Plan, rs: RuleSet, mode: str) -> str:
    n = sum(1 for a in plan.actions if a.change and a.kind != "note")
    day = date.strftime("%a %d %b").replace(" 0", " ")
    prefix = "REPLAY · " if mode == "replay" else ""
    if n == 0:
        return f"{prefix}AirDay {day}: no changes today"
    worst = plan.worst_band
    span = tu.fmt_ranges(plan.peak_hours) if plan.peak_hours else ""
    air = f". Air in the {rs.name(worst)} range {span}" if worst != UNKNOWN and span else ""
    if worst == UNKNOWN:
        air = ". Air data is missing, check the official AQI"
    return f"{prefix}AirDay {day}: {n} change{'s' if n != 1 else ''} today{air}"


def headline(plan: Plan, rs: RuleSet) -> str:
    if plan.worst_band == UNKNOWN:
        return "Air data is missing for today. Check the official AQI before outdoor activities."
    if plan.peak_pm25 is None:
        return f"Air expected in the {rs.name(plan.worst_band)} range."
    return (f"PM2.5 peaks around {round(plan.peak_pm25)} µg/m³ ({rs.name(plan.worst_band)} range) "
            f"{tu.fmt_ranges(plan.peak_hours)}.")


def to_brief(
    rs: RuleSet,
    plan: Plan,
    date: dt.date,
    official: Official,
    mode: str = "live",
    generated_at: str | None = None,
    upstream: dict[str, str] | None = None,
    school_name: str = "",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    labels = labels or {}
    station_band = aqimod.aqi_band(official.station_aqi) if official.station_aqi is not None else None
    city_band = aqimod.aqi_band(official.city_aqi) if official.city_aqi is not None else None
    actions = [{
        "ruleIds": a.rule_ids,
        "kind": a.kind,
        "activityId": a.activity_id,
        "label": labels.get(a.activity_id or "", None),
        "hours": a.hours,
        "band": a.band,
        "bandName": rs.name(a.band),
        "change": a.change,
        "text": a.text,
    } for a in plan.actions]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "rulesVersion": rs.version,
        "mode": mode,
        "date": date.isoformat(),
        "weekday": tu.weekday(date),
        "school": school_name,
        "generatedAt": generated_at or tu.now_ist().isoformat(timespec="seconds"),
        "subject": subject_line(date, plan, rs, mode),
        "headline": headline(plan, rs),
        "worstBand": plan.worst_band,
        "worstBandName": rs.name(plan.worst_band),
        "official": {
            "stationAqi": official.station_aqi,
            "stationBand": station_band,
            "stationBandName": rs.name(station_band) if station_band else None,
            "stationName": official.station_name,
            "stationAsOf": official.station_as_of,
            "cityAqi": official.city_aqi,
            "cityBand": city_band,
            "cityBandName": rs.name(city_band) if city_band else None,
            "citySource": official.city_source,
            "cityAsOf": official.city_as_of,
        },
        "grap": grap_info(official, date),
        "hours": [{
            "hour": h.hour,
            "pm25": h.pm25,
            "pm10": h.pm10,
            "band": h.band,
            "bandName": rs.name(h.band),
            "forecastBand": h.forecast_band,
            "stationPm25": h.station_pm25,
            "stationPm10": h.station_pm10,
            "escalated": h.escalated,
        } for h in plan.hours],
        "actions": actions,
        "parentNote": {
            "ruleId": plan.note_rule_id,
            "send": bool(plan.note_en),
            "optional": plan.note_optional,
            "en": plan.note_en,
            "hi": plan.note_hi,
            "addition": None,
        },
        "upstream": upstream or {},
    }
