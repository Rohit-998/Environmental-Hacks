"""Backtest the rules engine against what stations measured, Oct–Dec 2025, Delhi.

    uv run python -m backtest.run          # writes backtest/report.md and backtest/report.json

For every station and every school day (Mon–Sat), for each school hour 07:00–13:00, we compare the band
AirDay would have used with the band the station measured that hour. Three strategies:

  email       the 06:00 email: CAMS forecast only (station data at 06:00 doesn't reach school hours)
  live        the dashboard at the start of each hour: forecast + station escalation, 1-hour data lag
  persistence naive baseline: the 05:00 station reading applied to the whole day

The decision that matters is binary: should this hour be restricted? Two thresholds, matching the rules:
  Poor or worse       PE moves indoors (R-P-PE)
  Very Poor or worse  assembly and recess move indoors (R-VP-ASM, R-VP-REC)

Metrics: hit rate (POD, share of bad hours caught), false-alarm ratio (FAR, share of warnings that were
wrong) and critical success index (CSI). Same band engine as production: airday.rules.band_of and
airday.engine.hourly_bands.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from airday.engine import Reading, hourly_bands  # noqa: E402
from airday.rules import UNKNOWN, load  # noqa: E402

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
SCHOOL_HOURS = range(7, 14)
SCHOOL_DAYS = {0, 1, 2, 3, 4, 5}  # Mon–Sat
LAG_H = 1
RS = load()


@dataclass
class Counts:
    hit: int = 0
    miss: int = 0
    false_alarm: int = 0
    correct_neg: int = 0

    def add(self, predicted: bool, observed: bool) -> None:
        if predicted and observed:
            self.hit += 1
        elif observed:
            self.miss += 1
        elif predicted:
            self.false_alarm += 1
        else:
            self.correct_neg += 1

    @property
    def n(self) -> int:
        return self.hit + self.miss + self.false_alarm + self.correct_neg

    def summary(self) -> dict:
        pod = self.hit / (self.hit + self.miss) if self.hit + self.miss else None
        far = self.false_alarm / (self.hit + self.false_alarm) if self.hit + self.false_alarm else None
        csi = self.hit / (self.hit + self.miss + self.false_alarm) if self.hit + self.miss + self.false_alarm else None
        return {"n": self.n, "hit": self.hit, "miss": self.miss, "falseAlarm": self.false_alarm,
                "correctNeg": self.correct_neg, "pod": _r(pod), "far": _r(far), "csi": _r(csi),
                "observedRate": _r((self.hit + self.miss) / self.n) if self.n else None}


@dataclass
class Strategy:
    name: str
    poor: Counts = field(default_factory=Counts)
    vpoor: Counts = field(default_factory=Counts)
    exact: int = 0
    within_one: int = 0
    under: int = 0
    over: int = 0
    n: int = 0
    unknown: int = 0

    def add(self, pred: str, obs: str) -> None:
        if pred == UNKNOWN:
            self.unknown += 1
            return
        p, o = RS.rank(pred), RS.rank(obs)
        self.n += 1
        self.exact += p == o
        self.within_one += abs(p - o) <= 1
        self.under += p < o
        self.over += p > o
        self.poor.add(p >= RS.rank("poor"), o >= RS.rank("poor"))
        self.vpoor.add(p >= RS.rank("very_poor"), o >= RS.rank("very_poor"))

    def summary(self) -> dict:
        return {"name": self.name, "hours": self.n, "unknownHours": self.unknown,
                "exactBand": _r(self.exact / self.n), "withinOneBand": _r(self.within_one / self.n),
                "underPredicted": _r(self.under / self.n), "overPredicted": _r(self.over / self.n),
                "poorOrWorse": self.poor.summary(), "veryPoorOrWorse": self.vpoor.summary()}


def _r(x: float | None, nd: int = 3) -> float | None:
    return None if x is None else round(x, nd)


def bias_corrected(fc: list[Reading], station: list[Reading], cap: float = 4.0) -> dict[int, str]:
    """Scale the forecast by the station/forecast ratio over the last 3 known hours (capped), never below 1."""
    fc_by = {r.hour: r for r in fc}
    pairs = [(s.pm25, fc_by[s.hour].pm25) for s in station[-3:]
             if s.pm25 and s.hour in fc_by and fc_by[s.hour].pm25]
    k = min(cap, max(1.0, sum(a for a, _ in pairs) / sum(b for _, b in pairs))) if pairs else 1.0
    pm10_pairs = [(s.pm10, fc_by[s.hour].pm10) for s in station[-3:]
                  if s.pm10 and s.hour in fc_by and fc_by[s.hour].pm10]
    k10 = min(cap, max(1.0, sum(a for a, _ in pm10_pairs) / sum(b for _, b in pm10_pairs))) if pm10_pairs else 1.0
    return {r.hour: RS.band_of(r.pm25 * k if r.pm25 is not None else None,
                               r.pm10 * k10 if r.pm10 is not None else None) for r in fc}


def load_data():
    with gzip.open(os.path.join(DATA, "forecast.json.gz"), "rt", encoding="utf-8") as fh:
        fc = json.load(fh)
    forecast: dict[tuple[int, str], dict[int, tuple]] = defaultdict(dict)
    names = {}
    for loc, s in fc["stations"].items():
        names[int(loc)] = s["name"]
        h = s["hourly"]
        for t, p25, p10 in zip(h["time"], h["pm2_5"], h["pm10"], strict=True):
            day, hhmm = t.split("T")
            forecast[(int(loc), day)][int(hhmm[:2])] = (p25, p10)
    observed: dict[tuple[int, str], dict[int, tuple]] = defaultdict(dict)
    with gzip.open(os.path.join(DATA, "observed.csv.gz"), "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            f = lambda v: float(v) if v not in ("", None) else None  # noqa: E731
            observed[(int(r["station"]), r["date"])][int(r["hour"])] = (f(r["pm25"]), f(r["pm10"]))
    return fc["start"], fc["end"], names, forecast, observed


def run() -> dict:
    start, end, names, forecast, observed = load_data()
    strategies = {k: Strategy(k) for k in ("email", "email_floor", "email_ratio", "live", "persistence")}
    by_month: dict[str, Strategy] = defaultdict(lambda: Strategy("email"))
    pm25_err: list[float] = []
    mornings = Counts()  # day level: did the email restrict the morning when 08–10 was Very Poor+?
    days_scored = 0

    for (loc, day), obs_hours in sorted(observed.items()):
        d = dt.date.fromisoformat(day)
        if d.weekday() not in SCHOOL_DAYS or (loc, day) not in forecast:
            continue
        fc_hours = forecast[(loc, day)]
        fc_readings = [Reading(h, *fc_hours[h]) for h in sorted(fc_hours)]
        email = hourly_bands(RS, fc_readings)
        persist = RS.band_of(*obs_hours[5]) if 5 in obs_hours else UNKNOWN
        # What the 06:00 run knows: station hours up to 05:00 minus the lag.
        # Hour x ends at x+1:00 and arrives LAG_H later, so at 06:00 we know hours x <= 5 - LAG_H.
        at6 = [Reading(x, *obs_hours[x]) for x in sorted(obs_hours) if x <= 5 - LAG_H]
        floor = hourly_bands(RS, fc_readings, at6, max((r.hour for r in at6), default=None), escalation_hours=24)
        ratio = bias_corrected(fc_readings, at6)
        days_scored += 1
        morning_obs, morning_pred = [], []

        for h in SCHOOL_HOURS:
            if h not in obs_hours:
                continue
            obs_band = RS.band_of(*obs_hours[h])
            if obs_band == UNKNOWN:
                continue
            strategies["email"].add(email[h].band if h in email else UNKNOWN, obs_band)
            strategies["email_floor"].add(floor[h].band if h in floor else UNKNOWN, obs_band)
            strategies["email_ratio"].add(ratio.get(h, UNKNOWN), obs_band)
            by_month[day[:7]].add(email[h].band if h in email else UNKNOWN, obs_band)

            # Live: at h:00, station readings up to hour h-1-LAG are known.
            known_up_to = h - 1 - LAG_H
            station = [Reading(x, *obs_hours[x]) for x in sorted(obs_hours) if x <= known_up_to]
            st_hour = max((r.hour for r in station), default=None)
            if st_hour is not None and (h - st_hour - 1) * 60 > 120:
                st_hour = None  # same freshness limit as production (STATION_MAX_AGE_MIN)
            live = hourly_bands(RS, fc_readings, station, st_hour)
            strategies["live"].add(live[h].band if h in live else UNKNOWN, obs_band)

            strategies["persistence"].add(persist, obs_band)

            p25_fc, p25_obs = fc_hours.get(h, (None, None))[0], obs_hours[h][0]
            if p25_fc is not None and p25_obs is not None:
                pm25_err.append(p25_fc - p25_obs)
            if h in (8, 9):
                morning_obs.append(obs_band)
                if h in email:
                    morning_pred.append(email[h].band)

        if morning_obs and morning_pred and UNKNOWN not in morning_pred:
            o = max(RS.rank(b) for b in morning_obs) >= RS.rank("very_poor")
            p = max(RS.rank(b) for b in morning_pred) >= RS.rank("very_poor")
            mornings.add(p, o)

    n = len(pm25_err)
    return {
        "period": {"start": start, "end": end},
        "stations": sorted(names.values()),
        "stationDaysScored": days_scored,
        "lagHours": LAG_H,
        "strategies": [s.summary() for s in strategies.values()],
        "byMonth": {m: s.summary() for m, s in sorted(by_month.items())},
        "pm25": {"hours": n, "meanBias": _r(sum(pm25_err) / n, 1), "mae": _r(sum(abs(e) for e in pm25_err) / n, 1)},
        "morningPeDays": mornings.summary(),
    }


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:.0f}%"


def report_md(r: dict) -> str:
    s = {x["name"]: x for x in r["strategies"]}
    label = {"email": "06:00 email, forecast only",
             "email_floor": "06:00 email, latest station band as a floor for the day",
             "email_ratio": "06:00 email, forecast scaled by station/forecast ratio",
             "live": f"Live dashboard, forecast + station escalation ({r['lagHours']} h lag)",
             "persistence": "Baseline: 05:00 station reading all day"}
    lines = [
        "# Backtest: AirDay plans vs measured air, Delhi, Oct–Dec 2025",
        "",
        "Generated by `uv run python -m backtest.run`. Data is committed under `backtest/data/` so anyone can rerun it.",
        "",
        f"- Period: {r['period']['start']} to {r['period']['end']}, school days (Mon–Sat), school hours 07:00–13:00.",
        f"- Stations ({len(r['stations'])}): {', '.join(r['stations'])}.",
        f"- Station-days scored: {r['stationDaysScored']}.",
        "- Forecast: CAMS Global via Open-Meteo (archived forecasts, ~45 km, 3-hourly interpolated to hourly).",
        "- Observed: OpenAQ public archive of CPCB/DPCC/IMD 15-minute data, averaged to hours (75% completeness).",
        "- Bands: the production engine (`airday.rules`, `airday.engine`), worse of PM2.5 and PM10.",
        "",
        "## Should this hour be restricted?",
        "",
        "Hit rate = share of genuinely bad hours that AirDay flagged. False alarms = share of AirDay's warnings that turned out fine.",
        "",
        "| Strategy | Hours | Poor+ hit rate | Poor+ false alarms | Very Poor+ hit rate | Very Poor+ false alarms | Band exact | Within one band | Under-predicted |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for k in ("email", "email_floor", "email_ratio", "live", "persistence"):
        x = s[k]
        lines.append(
            f"| {label[k]} | {x['hours']} | {_pct(x['poorOrWorse']['pod'])} | {_pct(x['poorOrWorse']['far'])} | "
            f"{_pct(x['veryPoorOrWorse']['pod'])} | {_pct(x['veryPoorOrWorse']['far'])} | {_pct(x['exactBand'])} | "
            f"{_pct(x['withinOneBand'])} | {_pct(x['underPredicted'])} |")
    m = r["morningPeDays"]
    fl = s["email_floor"]
    lines += [
        "",
        f"Observed share of school hours that were Poor or worse: {_pct(s['email']['poorOrWorse']['observedRate'])}; "
        f"Very Poor or worse: {_pct(s['email']['veryPoorOrWorse']['observedRate'])}.",
        "",
        "## Decision",
        "",
        f"The forecast alone misses most bad hours: CAMS reads far cleaner than Delhi stations in winter (bias below). "
        f"So the production 06:00 brief uses the latest fresh station band as a floor for the rest of the school day "
        f"(`STATION_FLOOR_HOURS`, default 24). That is row 2: Very Poor+ hit rate {_pct(fl['veryPoorOrWorse']['pod'])} "
        f"at {_pct(fl['veryPoorOrWorse']['far'])} false alarms, up from {_pct(s['email']['veryPoorOrWorse']['pod'])}. "
        "We chose the floor over the ratio method because missing a bad hour costs more than an unneeded indoor PE period.",
        "",
        "A naive persistence baseline scores about as well. AirDay's value is not a better forecast: it is turning the "
        "reading into a timetable decision, before 07:00, with a parent note and a rule ID on every line.",
        "",
        "## Morning PE (08:00–10:00), day level, 06:00 email, forecast only",
        "",
        f"On {m['hit'] + m['miss']} station-days the 08:00–10:00 air was Very Poor or worse. The email moved PE indoors on "
        f"{m['hit']} of them ({_pct(m['pod'])}). Of the {m['hit'] + m['falseAlarm']} mornings it flagged, "
        f"{m['falseAlarm']} were not Very Poor ({_pct(m['far'])} false alarms).",
        "",
        "## Forecast bias",
        "",
        f"CAMS PM2.5 vs station, school hours: mean bias {r['pm25']['meanBias']:+} µg/m³, mean absolute error "
        f"{r['pm25']['mae']} µg/m³ over {r['pm25']['hours']} hours. Negative bias means the forecast reads cleaner than reality.",
        "",
        "## By month (06:00 email)",
        "",
        "| Month | Hours | Very Poor+ hit rate | Very Poor+ false alarms | Under-predicted |",
        "|---|---|---|---|---|",
    ]
    for month, x in r["byMonth"].items():
        lines.append(f"| {month} | {x['hours']} | {_pct(x['veryPoorOrWorse']['pod'])} | {_pct(x['veryPoorOrWorse']['far'])} | {_pct(x['underPredicted'])} |")
    lines += [
        "",
        "## Limits",
        "",
        "- Archived CAMS forecasts are the closest-lead forecast for each hour, so the email strategy is slightly flattered "
        "versus a forecast issued at 06:00.",
        "- Holidays and GRAP school closures are not removed; every Mon–Sat counts as a school day.",
        "- Stations are scored separately; nearby stations share a forecast grid cell, so results are correlated.",
        "- The 1-hour lag for station data is an assumption until the Thursday lag measurement replaces it.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    r = run()
    with open(os.path.join(HERE, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(HERE, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report_md(r))
    print(report_md(r))


if __name__ == "__main__":
    main()
