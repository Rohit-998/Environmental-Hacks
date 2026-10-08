"""The rules engine: a pure function from (timetable, hourly data, station readings) to a day plan.

No network, no AWS, no clock. Everything it needs is passed in, so it is easy to test and replay.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import timeutil as tu
from .rules import ACTIVITY_SCOPES, UNKNOWN, RuleSet

DEFAULT_ESCALATION_HOURS = 3


@dataclass(frozen=True)
class Activity:
    id: str
    day: str
    start: str
    end: str
    type: str
    label: str


@dataclass(frozen=True)
class Reading:
    """Hourly PM concentrations in µg/m³ for hour h, i.e. [h:00, h+1:00) IST."""
    hour: int
    pm25: float | None
    pm10: float | None


@dataclass
class HourBand:
    hour: int
    pm25: float | None
    pm10: float | None
    band: str
    forecast_band: str
    station_pm25: float | None = None
    station_pm10: float | None = None
    escalated: bool = False


@dataclass
class Action:
    rule_ids: list[str]
    kind: str  # activity | window | note
    text: str
    change: bool
    band: str
    activity_id: str | None = None
    hours: list[int] = field(default_factory=list)


@dataclass
class Plan:
    date: str
    hours: list[HourBand]
    actions: list[Action]
    worst_band: str
    note_rule_id: str
    note_en: str
    note_hi: str
    note_optional: bool
    peak_pm25: float | None
    peak_hours: list[int]


def hourly_bands(
    rs: RuleSet,
    forecast: list[Reading],
    station: list[Reading] | None = None,
    station_hour: int | None = None,
    escalation_hours: int = DEFAULT_ESCALATION_HOURS,
) -> dict[int, HourBand]:
    """Band per hour from the forecast, then raise bands from the latest fresh station reading.

    station_hour is the hour of the latest station reading that is fresh enough to use (the caller
    applies the age limit). Escalation only ever raises a band and also fills unknown hours.
    """
    out: dict[int, HourBand] = {}
    for r in forecast:
        b = rs.band_of(r.pm25, r.pm10)
        out[r.hour] = HourBand(hour=r.hour, pm25=r.pm25, pm10=r.pm10, band=b, forecast_band=b)
    for s in station or []:
        hb = out.setdefault(s.hour, HourBand(s.hour, None, None, UNKNOWN, UNKNOWN))
        hb.station_pm25, hb.station_pm10 = s.pm25, s.pm10

    if station_hour is not None and station_hour in out:
        latest = out[station_hour]
        s_band = rs.band_of(latest.station_pm25, latest.station_pm10)
        if s_band != UNKNOWN:
            for h in range(station_hour, station_hour + escalation_hours):
                hb = out.setdefault(h, HourBand(h, None, None, UNKNOWN, UNKNOWN))
                if hb.band == UNKNOWN or rs.rank(s_band) > rs.rank(hb.band):
                    hb.band = s_band
                    hb.escalated = True
    return out


def activity_band(rs: RuleSet, bands: dict[int, HourBand], hours: list[int]) -> str:
    """Worst known band across the hours. Fail safe: Very Poor or worse wins over unknown;
    otherwise any unknown hour makes the whole activity unknown."""
    known = [bands[h].band for h in hours if h in bands and bands[h].band != UNKNOWN]
    has_unknown = len(known) < len(hours)
    if not known:
        return UNKNOWN
    worst = max(known, key=rs.rank)
    if has_unknown and rs.rank(worst) < rs.rank("very_poor"):
        return UNKNOWN
    return worst


def _render(template: str, **kw: str) -> str:
    return template.format(**kw)


def build_plan(
    rs: RuleSet,
    date: str,
    school_start: str,
    school_end: str,
    activities: list[Activity],
    bands: dict[int, HourBand],
) -> Plan:
    s_min, e_min = tu.parse_hhmm(school_start), tu.parse_hhmm(school_end)
    school_hours = tu.hours_overlapped(s_min, e_min)
    actions: list[Action] = []

    # Activity-bound actions, in time order.
    for a in sorted(activities, key=lambda x: (tu.parse_hhmm(x.start), x.label)):
        if a.type not in ACTIVITY_SCOPES:
            raise ValueError(f"activity {a.id} has unknown type {a.type!r}")
        hrs = tu.hours_overlapped(tu.parse_hhmm(a.start), tu.parse_hhmm(a.end))
        band = activity_band(rs, bands, hrs)
        rule = rs.rule(band, a.type)
        actions.append(Action(
            rule_ids=[rule.id], kind="activity", activity_id=a.id, hours=hrs, band=band,
            change=rule.change, text=_render(rule.en, label=a.label, start=a.start, end=a.end),
        ))

    # Window actions: merge contiguous school hours with the same instruction.
    runs: list[dict] = []
    for h in school_hours:
        band = bands[h].band if h in bands else UNKNOWN
        rule = rs.rule(band, "window")
        if runs and runs[-1]["instruction"] == rule.instruction and runs[-1]["hours"][-1] == h - 1:
            run = runs[-1]
            run["hours"].append(h)
            if rule.id not in run["rule_ids"]:
                run["rule_ids"].append(rule.id)
            if rs_rank_safe(rs, band) > rs_rank_safe(rs, run["band"]):
                run["band"] = band
            run["change"] = run["change"] or rule.change
        else:
            runs.append({"instruction": rule.instruction, "hours": [h], "rule_ids": [rule.id],
                         "band": band, "change": rule.change})
    for run in runs:
        start = max(run["hours"][0] * 60, s_min)
        end = min((run["hours"][-1] + 1) * 60, e_min)
        rule = rs.rules[run["rule_ids"][0]]
        actions.append(Action(
            rule_ids=run["rule_ids"], kind="window", hours=run["hours"], band=run["band"],
            change=run["change"], text=_render(rule.en, start=tu.fmt_hhmm(start), end=tu.fmt_hhmm(end)),
        ))

    # Parent note: worst known band in school hours, once per day.
    known = [bands[h].band for h in school_hours if h in bands and bands[h].band != UNKNOWN]
    worst = max(known, key=rs.rank) if known else UNKNOWN
    note_rule = rs.rule(worst, "note")
    worst_hours = [h for h in school_hours if h in bands and bands[h].band == worst]
    hours_text = tu.fmt_ranges(worst_hours)
    note_en = _render(note_rule.en, hours=hours_text) if note_rule.emit else ""
    note_hi = _render(note_rule.hi, hours=hours_text) if note_rule.emit else ""
    actions.append(Action(
        rule_ids=[note_rule.id], kind="note", hours=worst_hours, band=worst,
        change=note_rule.change, text=note_en or "No parent note needed today.",
    ))

    pm = [(bands[h].pm25, h) for h in school_hours if h in bands and bands[h].pm25 is not None]
    peak = max(pm)[0] if pm else None

    return Plan(
        date=date,
        hours=[bands[h] for h in sorted(bands)],
        actions=actions,
        worst_band=worst,
        note_rule_id=note_rule.id,
        note_en=note_en,
        note_hi=note_hi,
        note_optional=note_rule.optional,
        peak_pm25=peak,
        peak_hours=worst_hours,
    )


def rs_rank_safe(rs: RuleSet, band: str) -> int:
    """Rank with unknown treated as worse than everything, for window run labels only."""
    return len(rs.order) if band == UNKNOWN else rs.rank(band)
