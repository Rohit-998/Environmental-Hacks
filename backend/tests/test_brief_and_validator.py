import datetime as dt
import json
import os

import jsonschema
import pytest

from airday.brief import Official, to_brief
from airday.engine import Activity, Reading, build_plan, hourly_bands
from airday.rules import load
from airday.validator import BriefInvalid, assert_valid, check_brief, check_chat, check_translation

RS = load()
SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "brief.schema.json"),
                        encoding="utf-8"))
ACTS = [
    Activity("a1", "Thu", "07:50", "08:10", "assembly", "Morning assembly"),
    Activity("a2", "Thu", "08:40", "09:20", "pe", "Class 6B PE"),
    Activity("a3", "Thu", "13:00", "13:40", "pe", "Class 8A PE"),
]
DATE = dt.date(2025, 11, 20)


def make(pm25=None, official=None, mode="live"):
    pm25 = pm25 or {7: 140, 8: 140, 9: 130, 10: 125, 11: 100, 12: 85, 13: 80}
    bands = hourly_bands(RS, [Reading(h, v, None) for h, v in pm25.items()])
    plan = build_plan(RS, DATE.isoformat(), "07:45", "14:00", ACTS, bands)
    return to_brief(RS, plan, DATE, official or Official(station_aqi=284, city_aqi=310), mode=mode,
                    generated_at="2025-11-20T06:00:00+05:30")


def test_brief_matches_schema_and_is_valid():
    b = make()
    jsonschema.validate(b, SCHEMA)
    assert check_brief(RS, b, [a.id for a in ACTS]) == []


def test_subject_carries_the_decision():
    b = make()
    assert b["subject"].startswith("AirDay Thu 20 Nov: 3 changes today. Air in the Very Poor range")
    assert make(mode="replay")["subject"].startswith("REPLAY · AirDay")
    clean = make({h: 20 for h in range(7, 14)})
    assert clean["subject"] == "AirDay Thu 20 Nov: no changes today"


def test_headline_never_calls_an_hourly_number_aqi():
    b = make()
    assert "AQI" not in b["headline"] and "µg/m³" in b["headline"]


def test_grap_indicative_and_override_expiry():
    assert make()["grap"] == {"stage": "II", "kind": "indicative",
                              "label": "Indicative GRAP Stage II (from Delhi average AQI, not a CAQM order)"}
    ov = {"stage": "III", "setAt": "2025-11-19", "expiresAt": "2025-11-21"}
    assert make(official=Official(city_aqi=310, grap_override=ov))["grap"]["kind"] == "official"
    ov["expiresAt"] = "2025-11-19"
    assert make(official=Official(city_aqi=310, grap_override=ov))["grap"]["kind"] == "indicative"


def test_validator_rejects_bad_briefs():
    ids = [a.id for a in ACTS]
    b = make()
    b["actions"][0]["ruleIds"] = ["R-XX-PE"]
    assert any("unknown rule" in p for p in check_brief(RS, b, ids))

    b = make()
    b["actions"][0]["ruleIds"] = []
    assert any("no rule ID" in p for p in check_brief(RS, b, ids))

    b = make()
    b["actions"] = [a for a in b["actions"] if a["activityId"] != "a2"]
    assert any("a2 has 0 actions" in p for p in check_brief(RS, b, ids))

    b = make()
    b["headline"] = "AQI 330 this morning"
    with pytest.raises(BriefInvalid):
        assert_valid(RS, b, ids)


def test_chat_grounding():
    assert check_chat({"answer": "ok", "ruleIds": ["R-MOD-PE"]}, {"R-MOD-PE"}, True) == []
    assert check_chat({"answer": "ok", "ruleIds": []}, {"R-MOD-PE"}, True)
    assert check_chat({"answer": "ok", "ruleIds": ["R-VP-PE"]}, {"R-MOD-PE"}, True)
    assert check_chat({"answer": "Hello", "ruleIds": []}, set(), False) == []
    assert check_chat("plain text", set(), False)


def test_translation_check():
    en = "Annual day rehearsal moved to Monday at 09:30, bring 2 copies."
    assert check_translation(en, "वार्षिक दिवस का अभ्यास सोमवार ०९:३० बजे होगा, 2 प्रतियाँ लाएँ।") == []
    assert check_translation(en, "वार्षिक दिवस का अभ्यास सोमवार 9:30 बजे होगा, दो प्रतियाँ लाएँ।")
    assert check_translation(en, en)
    assert check_translation(en, "")
