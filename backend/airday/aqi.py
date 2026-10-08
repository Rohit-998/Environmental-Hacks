"""Official CPCB AQI (24-hour basis) and the indicative GRAP stage.

These are display-only. Nothing in this module feeds the timetable rules.
"""
from __future__ import annotations

# CPCB AQI categories on the 0-500 index scale.
AQI_BANDS = (
    (50, "good"),
    (100, "satisfactory"),
    (200, "moderate"),
    (300, "poor"),
    (400, "very_poor"),
)

# CAQM GRAP stage thresholds on Delhi's average AQI. Confirm against the current schedule (SOURCES.md: caqm_grap).
GRAP_STAGES = ((450, "IV"), (400, "III"), (300, "II"), (200, "I"))

PM_POLLUTANTS = {"PM2.5", "PM10"}


def aqi_band(aqi: float) -> str:
    for upper, band in AQI_BANDS:
        if aqi <= upper:
            return band
    return "severe"


def station_aqi(sub_indices: dict[str, float | None]) -> int | None:
    """CPCB rule: the AQI is the highest sub-index, and is only reported when at least
    three pollutants have data and one of them is PM2.5 or PM10."""
    present = {k: float(v) for k, v in sub_indices.items() if v is not None}
    if len(present) < 3 or not (PM_POLLUTANTS & present.keys()):
        return None
    return round(max(present.values()))


def city_average(aqis: list[int | None]) -> int | None:
    vals = [a for a in aqis if a is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals))


def grap_stage(city_aqi: int | None) -> str | None:
    """Indicative stage from the Delhi average AQI. None below 201."""
    if city_aqi is None:
        return None
    for lower, stage in GRAP_STAGES:
        if city_aqi > lower:
            return stage
    return None
