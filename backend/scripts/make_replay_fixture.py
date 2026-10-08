"""Freeze Open-Meteo data for a replay date (plus the next 2 days for chat) into fixtures/replay/<date>.json.

    uv run python scripts/make_replay_fixture.py 2025-11-19

The CPCB bulletin city AQI is NOT fetched: it must be read from the bulletin PDF by a person and
entered by hand into `official.cityAqi` with `official.cityAsOf`. Until then it stays null and the UI
shows "unavailable". Never enter it from memory.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from airday import sources  # noqa: E402

# Rohini, Delhi (demo school locality).
LAT, LON = 28.7383, 77.0822
OUT = os.path.join(os.path.dirname(__file__), "..", "fixtures", "replay")


def main(date: str) -> None:
    d = dt.date.fromisoformat(date)
    end = (d + dt.timedelta(days=2)).isoformat()
    raw = sources.fetch_open_meteo(LAT, LON, date, end)
    path = os.path.join(OUT, f"{date}.json")
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            existing = json.load(fh)
    fixture = {
        "date": date,
        "lat": LAT,
        "lon": LON,
        "openMeteo": raw,
        "openaq": existing.get("openaq", {"pm25": {}, "pm10": {}, "note": "no archived station data"}),
        "official": existing.get("official", {
            "cityAqi": None,
            "cityAsOf": None,
            "citySource": "bulletin",
            "note": "Fill from the CPCB daily bulletin of the previous day (published ~16:00).",
        }),
    }
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fixture, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        main(arg)
