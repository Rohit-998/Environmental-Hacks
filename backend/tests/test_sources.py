import json
import os

from airday import sources

FIX = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "replay", "2025-11-19.json")


def test_parse_open_meteo_fixture_groups_by_ist_date():
    raw = json.load(open(FIX, encoding="utf-8"))["openMeteo"]
    days = sources.parse_open_meteo(raw)
    assert "2025-11-19" in days
    hours = [r.hour for r in days["2025-11-19"]]
    assert hours == list(range(24))
    assert raw["timezone"] == "Asia/Kolkata"


def test_open_meteo_url_requests_ist_and_date_range():
    url = sources.open_meteo_url(28.7, 77.1, "2025-11-19", "2025-11-21")
    assert "timezone=Asia%2FKolkata" in url and "start_date=2025-11-19" in url and "pm2_5%2Cpm10" in url


def test_parse_openaq_hours_converts_utc_to_ist_start_hour():
    raw = {"results": [
        {"value": 150.0, "period": {"datetimeFrom": {"utc": "2025-11-19T02:30:00Z"}}},
        {"value": None, "period": {"datetimeFrom": {"utc": "2025-11-19T03:30:00Z"}}},
    ]}
    assert sources.parse_openaq_hours(raw) == {8: 150.0}


def test_parse_data_gov_computes_station_aqi():
    raw = {"records": [
        {"station": "Rohini, Delhi - DPCC", "pollutant_id": "PM2.5", "avg_value": "312", "last_update": "19-11-2025 05:00:00"},
        {"station": "Rohini, Delhi - DPCC", "pollutant_id": "PM10", "avg_value": "280", "last_update": "19-11-2025 05:00:00"},
        {"station": "Rohini, Delhi - DPCC", "pollutant_id": "NO2", "avg_value": "NA", "last_update": "19-11-2025 05:00:00"},
        {"station": "Rohini, Delhi - DPCC", "pollutant_id": "CO", "avg_value": "70", "last_update": "19-11-2025 05:00:00"},
        {"station": "Dwarka", "pollutant_id": "PM2.5", "avg_value": "300"},
    ]}
    st = sources.parse_data_gov(raw)
    assert st["Rohini, Delhi - DPCC"]["aqi"] == 312
    assert st["Dwarka"]["aqi"] is None
