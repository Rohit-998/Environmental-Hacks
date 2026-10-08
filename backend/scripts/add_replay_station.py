"""Copy a station's measured hourly PM2.5/PM10 from the backtest archive into replay fixtures.

    uv run python scripts/add_replay_station.py 2025-11-19 2025-11-27

Uses the DTU, New Delhi - CPCB station (OpenAQ location 5626), about 3 km from the demo school in Rohini. The
data comes from the OpenAQ public archive already committed under backtest/data/. The replay brief only uses
hours before 06:00 (what a 06:00 run would have known); later hours feed the dashboard's station overlay.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
OBSERVED = os.path.join(BACKEND, "backtest", "data", "observed.csv.gz")
FIXTURES = os.path.join(BACKEND, "fixtures", "replay")
STATION_ID, STATION_NAME = "5626", "DTU, New Delhi - CPCB"


def main(dates: list[str]) -> None:
    with gzip.open(OBSERVED, "rt", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["station"] == STATION_ID and r["date"] in dates]
    for date in dates:
        path = os.path.join(FIXTURES, f"{date}.json")
        with open(path, encoding="utf-8") as fh:
            fx = json.load(fh)
        pm25 = {r["hour"]: float(r["pm25"]) for r in rows if r["date"] == date and r["pm25"]}
        pm10 = {r["hour"]: float(r["pm10"]) for r in rows if r["date"] == date and r["pm10"]}
        fx["openaq"] = {
            "station": STATION_NAME,
            "openaqLocationId": int(STATION_ID),
            "source": "OpenAQ public archive (s3://openaq-data-archive), 15-minute data averaged to hours",
            "pm25": pm25,
            "pm10": pm10,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(fx, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print(f"{date}: {len(pm25)} PM2.5 hours, {len(pm10)} PM10 hours from {STATION_NAME}")


if __name__ == "__main__":
    main(sys.argv[1:])
