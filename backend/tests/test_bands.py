import pytest

from airday import timeutil as tu
from airday.rules import UNKNOWN, load

RS = load()


@pytest.mark.parametrize("pm25,band", [
    (0, "good"), (30, "good"), (30.01, "satisfactory"), (60, "satisfactory"),
    (90, "moderate"), (90.4, "poor"), (120, "poor"), (120.5, "very_poor"),
    (250, "very_poor"), (250.01, "severe"), (999, "severe"),
])
def test_pm25_band_edges(pm25, band):
    assert RS.band_of(pm25, None) == band


@pytest.mark.parametrize("pm10,band", [
    (50, "good"), (50.1, "satisfactory"), (100, "satisfactory"), (250, "moderate"),
    (350, "poor"), (430, "very_poor"), (430.1, "severe"),
])
def test_pm10_band_edges(pm10, band):
    assert RS.band_of(None, pm10) == band


def test_worse_of_the_two_pollutants_wins():
    assert RS.band_of(40, 360) == "very_poor"
    assert RS.band_of(130, 60) == "very_poor"


@pytest.mark.parametrize("bad", [None, -1, 1001, "x"])
def test_invalid_values_are_missing(bad):
    assert RS.band_of(bad, 60) == "satisfactory"
    assert RS.band_of(bad, None) == UNKNOWN


def test_hours_overlapped():
    assert tu.hours_overlapped(8 * 60 + 40, 9 * 60 + 20) == [8, 9]
    assert tu.hours_overlapped(8 * 60, 9 * 60) == [8]
    assert tu.hours_overlapped(8 * 60, 8 * 60) == []


def test_utc_to_ist():
    assert tu.to_ist("2025-11-20T02:30:00Z").strftime("%H:%M") == "08:00"


def test_fmt_ranges():
    assert tu.fmt_ranges([8, 9, 10, 13]) == "08:00–11:00, 13:00–14:00"
