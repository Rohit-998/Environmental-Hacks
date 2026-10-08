"""Download backtest data: Oct–Dec 2025, Delhi.

    uv run python -m backtest.fetch

Writes two compact, committed files so the backtest reruns offline:
  backtest/data/observed.csv.gz  hourly PM2.5/PM10 per CPCB/DPCC station (OpenAQ public archive on S3)
  backtest/data/forecast.json.gz Open-Meteo CAMS Global hourly PM2.5/PM10 at each station's coordinates

Assumptions (stated in the report):
  - OpenAQ archive `datetime` is the END of each 15-minute period, so a reading stamped 09:00 belongs to hour 08.
  - An hourly average needs at least 3 of 4 quarter-hours (75% completeness), otherwise the hour is missing.
  - Values <= 0 or > 1000 µg/m³ are dropped, matching the rules engine.
"""
from __future__ import annotations

import concurrent.futures as cf
import csv
import datetime as dt
import gzip
import io
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from airday import sources  # noqa: E402

START, END = dt.date(2025, 10, 1), dt.date(2025, 12, 31)
ARCHIVE = "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid={id}/year={y}/month={m:02d}/location-{id}-{ymd}.csv.gz"
OUT = os.path.join(os.path.dirname(__file__), "data")

# OpenAQ location IDs for Delhi reference stations (CPCB/DPCC/IMD). DTU is ~3 km from the demo school in Rohini.
STATIONS = {
    5626: "DTU, New Delhi - CPCB",
    10486: "Mundka, Delhi - DPCC",
    8235: "Jahangirpuri, Delhi - DPCC",
    8915: "Wazirpur, Delhi - DPCC",
    50: "Punjabi Bagh, Delhi - DPCC",
    5610: "North Campus, DU, Delhi - IMD",
    5586: "Sirifort, Delhi - CPCB",
    5634: "Lodhi Road, New Delhi - IMD",
    235: "Anand Vihar, New Delhi - DPCC",
}
VALID_MAX = 1000.0


def _day_file(loc: int, day: dt.date) -> list[dict]:
    url = ARCHIVE.format(id=loc, y=day.year, m=day.month, ymd=day.strftime("%Y%m%d"))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            text = gzip.decompress(r.read()).decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return []
        raise
    return list(csv.DictReader(io.StringIO(text)))


def hourly(rows: list[dict]) -> dict[tuple[str, int], dict[str, float]]:
    """{(IST date, hour): {"pm25": avg, "pm10": avg}} from 15-minute rows (end-of-period timestamps)."""
    buckets: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    for r in rows:
        param = r.get("parameter")
        if param not in ("pm25", "pm10"):
            continue
        try:
            v = float(r["value"])
        except (TypeError, ValueError):
            continue
        if not (0 < v <= VALID_MAX):
            continue
        end = dt.datetime.fromisoformat(r["datetime"]).astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30)))
        start = end - dt.timedelta(minutes=1)
        buckets[(start.date().isoformat(), start.hour, param)].append(v)
    out: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    for (day, hour, param), vals in buckets.items():
        if len(vals) >= 3:  # 75% of 4 quarter-hours
            out[(day, hour)][param] = round(sum(vals) / len(vals), 1)
    return out


def fetch_observed() -> list[dict]:
    days = [START + dt.timedelta(days=i) for i in range((END - START).days + 2)]  # +1 day for UTC spill-over
    jobs = [(loc, d) for loc in STATIONS for d in days]
    rows_by_loc: dict[int, list[dict]] = defaultdict(list)
    meta: dict[int, tuple[float, float]] = {}
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for (loc, _), rows in zip(jobs, ex.map(lambda j: _day_file(*j), jobs)):
            rows_by_loc[loc].extend(rows)
            if rows and loc not in meta:
                meta[loc] = (float(rows[0]["lat"]), float(rows[0]["lon"]))
    out = []
    for loc, rows in rows_by_loc.items():
        for (day, hour), v in sorted(hourly(rows).items()):
            if START.isoformat() <= day <= END.isoformat():
                out.append({"station": loc, "date": day, "hour": hour, "pm25": v.get("pm25"), "pm10": v.get("pm10")})
        print(f"{loc} {STATIONS[loc]}: {sum(1 for r in out if r['station'] == loc)} hours", file=sys.stderr)
    return out, meta


def fetch_forecast(meta: dict[int, tuple[float, float]]) -> dict:
    out = {}
    for loc, (lat, lon) in meta.items():
        raw = sources.fetch_open_meteo(lat, lon, START.isoformat(), END.isoformat())
        out[str(loc)] = {"name": STATIONS[loc], "lat": lat, "lon": lon,
                         "gridLat": raw.get("latitude"), "gridLon": raw.get("longitude"), "hourly": raw["hourly"]}
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    observed, meta = fetch_observed()
    with gzip.open(os.path.join(OUT, "observed.csv.gz"), "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["station", "date", "hour", "pm25", "pm10"])
        w.writeheader()
        w.writerows(observed)
    forecast = fetch_forecast(meta)
    with gzip.open(os.path.join(OUT, "forecast.json.gz"), "wt", encoding="utf-8") as fh:
        json.dump({"start": START.isoformat(), "end": END.isoformat(), "stations": forecast}, fh)
    print(f"wrote {len(observed)} observed hours and forecasts for {len(forecast)} stations", file=sys.stderr)


if __name__ == "__main__":
    main()
