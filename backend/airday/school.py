"""School profile and timetable: validation, CSV import, sample data."""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import uuid
from typing import Any

from . import timeutil as tu
from .engine import Activity
from .rules import ACTIVITY_SCOPES

MAX_ROWS = 200
DAY_ALIASES = {d.lower(): d for d in tu.DAYS} | {
    "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu",
    "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
}
TYPE_ALIASES = {
    "assembly": "assembly", "recess": "recess", "break": "recess", "lunch": "recess",
    "pe": "pe", "p.e.": "pe", "sports": "pe", "games": "pe", "physical education": "pe",
}

SAMPLE_PROFILE: dict[str, Any] = {
    "name": "Sunrise Public School",
    "locality": "Rohini, Delhi",
    "lat": 28.7383,
    "lon": 77.0822,
    "start": "07:45",
    "end": "14:00",
    "schoolDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    "holidays": [],
    "principalEmail": "",
    "cpcbStation": "Rohini, Delhi - DPCC",
    "openaqLocationId": None,
    "openaqSensors": {"pm25": None, "pm10": None},
    "grapOverride": None,
}

# Morning PE on every school day so any replay date shows the main recommendation.
_SAMPLE_CLASSES = {"Mon": "6B", "Tue": "7A", "Wed": "6B", "Thu": "6B", "Fri": "7A", "Sat": "8B"}
SAMPLE_CSV = "day,start,end,type,label\n" + "".join(
    f"{d},07:50,08:10,assembly,Morning assembly\n"
    f"{d},08:40,09:20,pe,Class {c} PE\n"
    f"{d},10:30,10:50,recess,Recess\n"
    f"{d},13:00,13:40,pe,Class 8A PE\n"
    for d, c in _SAMPLE_CLASSES.items()
)

PUBLIC_PROFILE_FIELDS = ("name", "locality", "lat", "lon", "start", "end", "schoolDays", "holidays",
                         "cpcbStation", "grapOverride")


def public_profile(p: dict) -> dict:
    """Never returns the principal's email."""
    return {k: p.get(k) for k in PUBLIC_PROFILE_FIELDS} | {"hasEmail": bool(p.get("principalEmail"))}


def validate_profile(p: dict) -> list[str]:
    errs = []
    if not str(p.get("name", "")).strip():
        errs.append("name is required")
    try:
        lat, lon = float(p.get("lat")), float(p.get("lon"))
        if not (6 <= lat <= 37 and 68 <= lon <= 98):
            errs.append("location must be in India")
    except (TypeError, ValueError):
        errs.append("lat and lon must be numbers")
    try:
        if tu.parse_hhmm(p.get("start", "")) >= tu.parse_hhmm(p.get("end", "")):
            errs.append("school start must be before end")
    except (ValueError, AttributeError):
        errs.append("school hours must be HH:MM")
    days = p.get("schoolDays") or []
    if not days or any(d not in tu.DAYS for d in days):
        errs.append("schoolDays must be a non-empty list of Mon..Sun")
    for h in p.get("holidays") or []:
        try:
            dt.date.fromisoformat(h)
        except ValueError:
            errs.append(f"holiday {h!r} is not YYYY-MM-DD")
    email = p.get("principalEmail") or ""
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errs.append("principalEmail is not a valid email")
    ov = p.get("grapOverride")
    if ov and ov.get("stage") not in ("I", "II", "III", "IV"):
        errs.append("grapOverride.stage must be I, II, III or IV")
    return errs


def is_school_day(profile: dict, date: dt.date) -> bool:
    return tu.weekday(date) in profile.get("schoolDays", []) and date.isoformat() not in profile.get("holidays", [])


# ---------------------------------------------------------------- timetable

def parse_timetable_csv(text: str, school_start: str, school_end: str) -> tuple[list[dict], list[dict]]:
    """Returns (rows, errors). Each error is {"line": n, "row": raw, "reason": str}.

    Accepts a header row or none, a UTF-8 BOM, tabs (Excel paste) or commas, 12-hour times with am/pm.
    """
    text = text.lstrip("﻿").strip()
    if not text:
        return [], [{"line": 0, "row": "", "reason": "timetable is empty"}]
    delim = "\t" if "\t" in text.splitlines()[0] else ","
    reader = list(csv.reader(io.StringIO(text), delimiter=delim))
    if reader and [c.strip().lower() for c in reader[0]][:4] == ["day", "start", "end", "type"]:
        reader = reader[1:]
        first_line = 2
    else:
        first_line = 1
    s_min, e_min = tu.parse_hhmm(school_start), tu.parse_hhmm(school_end)
    rows, errors = [], []
    if len(reader) > MAX_ROWS:
        return [], [{"line": 0, "row": "", "reason": f"more than {MAX_ROWS} rows"}]
    for i, raw in enumerate(reader):
        line = first_line + i
        if not any(c.strip() for c in raw):
            continue
        cells = [c.strip() for c in raw] + [""] * 5
        day_raw, start_raw, end_raw, type_raw, label = cells[:5]
        reason = None
        day = DAY_ALIASES.get(day_raw.lower())
        typ = TYPE_ALIASES.get(type_raw.lower())
        start = end = None
        if not day:
            reason = f"day {day_raw!r} is not Mon–Sun"
        elif not typ:
            reason = f"type {type_raw!r} must be assembly, recess or pe"
        else:
            try:
                start, end = _norm_time(start_raw), _norm_time(end_raw)
                if tu.parse_hhmm(start) >= tu.parse_hhmm(end):
                    reason = "start must be before end"
                elif tu.parse_hhmm(start) < s_min or tu.parse_hhmm(end) > e_min:
                    reason = f"outside school hours {school_start}–{school_end}"
            except ValueError:
                reason = f"times must be HH:MM (got {start_raw!r}, {end_raw!r})"
        if reason:
            errors.append({"line": line, "row": delim.join(raw), "reason": reason})
            continue
        rows.append({"day": day, "start": start, "end": end, "type": typ,
                     "label": label or _default_label(typ)})
    return rows, errors


def _norm_time(s: str) -> str:
    s = s.strip().lower().replace(".", ":")
    m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(am|pm)?", s)
    if not m:
        raise ValueError(s)
    h, mm, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm:
        if not 1 <= h <= 12:
            raise ValueError(s)
        h = h % 12 + (12 if ampm == "pm" else 0)
    out = f"{h:02d}:{mm:02d}"
    tu.parse_hhmm(out)
    return out


def _default_label(typ: str) -> str:
    return {"assembly": "Assembly", "recess": "Recess", "pe": "PE"}[typ]


def with_ids(rows: list[dict]) -> list[dict]:
    return [r | {"id": r.get("id") or uuid.uuid4().hex[:8]} for r in rows]


def validate_rows(rows: list[dict], school_start: str, school_end: str) -> list[dict]:
    """Validate JSON rows by round-tripping them through the CSV parser."""
    text = "\n".join(",".join(str(r.get(k, "")) for k in ("day", "start", "end", "type", "label")) for r in rows)
    _, errors = parse_timetable_csv(text, school_start, school_end)
    return errors


def activities_for(rows: list[dict], date: dt.date) -> list[Activity]:
    day = tu.weekday(date)
    return [Activity(r["id"], r["day"], r["start"], r["end"], r["type"], r["label"])
            for r in rows if r["day"] == day and r["type"] in ACTIVITY_SCOPES]
