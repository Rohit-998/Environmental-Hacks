import datetime as dt

import pytest

from airday import school
from airday.store import ConditionFailed, MemoryStore


def test_sample_csv_parses_cleanly_with_morning_pe_every_school_day():
    rows, errs = school.parse_timetable_csv(school.SAMPLE_CSV, "07:45", "14:00")
    assert errs == []
    for d in school.SAMPLE_PROFILE["schoolDays"]:
        assert any(r["day"] == d and r["type"] == "pe" and r["start"] < "10:00" for r in rows)


def test_csv_reports_bad_rows_with_reasons_and_accepts_excel_paste():
    text = ("﻿day\tstart\tend\ttype\tlabel\n"
            "Monday\t8:40 am\t9:20 AM\tSports\tClass 6B\n"
            "Funday\t08:00\t08:30\tpe\tX\n"
            "Mon\t09:00\t08:00\tpe\tX\n"
            "Mon\t06:00\t06:30\tpe\tX\n"
            "Mon\t08:00\t08:30\tswimming\tX\n")
    rows, errs = school.parse_timetable_csv(text, "07:45", "14:00")
    assert rows == [{"day": "Mon", "start": "08:40", "end": "09:20", "type": "pe", "label": "Class 6B"}]
    reasons = [e["reason"] for e in errs]
    assert [e["line"] for e in errs] == [3, 4, 5, 6]
    assert "not Mon–Sun" in reasons[0] and "before end" in reasons[1]
    assert "outside school hours" in reasons[2] and "must be assembly" in reasons[3]


def test_public_profile_hides_email():
    p = school.SAMPLE_PROFILE | {"principalEmail": "p@example.com"}
    pub = school.public_profile(p)
    assert "principalEmail" not in pub and pub["hasEmail"] is True


def test_profile_validation():
    assert school.validate_profile(school.SAMPLE_PROFILE) == []
    bad = school.SAMPLE_PROFILE | {"lat": 51.5, "start": "15:00", "principalEmail": "nope"}
    errs = school.validate_profile(bad)
    assert len(errs) == 3


def test_school_days_and_holidays():
    p = school.SAMPLE_PROFILE | {"holidays": ["2025-11-21"]}
    assert school.is_school_day(p, dt.date(2025, 11, 20))
    assert not school.is_school_day(p, dt.date(2025, 11, 21))
    assert not school.is_school_day(p, dt.date(2025, 11, 23))  # Sunday


def test_email_claim_protocol():
    s = MemoryStore()
    s.claim_email("S", "EMAIL#d", 1.0, 3)
    with pytest.raises(ConditionFailed):
        s.claim_email("S", "EMAIL#d", 2.0, 3)
    s.set_email_status("S", "EMAIL#d", "FAILED", 3.0)
    assert s.claim_email("S", "EMAIL#d", 4.0, 3)["attempts"] == 2
    s.set_email_status("S", "EMAIL#d", "SENT", 5.0)
    with pytest.raises(ConditionFailed):
        s.claim_email("S", "EMAIL#d", 6.0, 3)


def test_failed_claims_stop_at_max_attempts():
    s = MemoryStore()
    for _ in range(3):
        s.claim_email("S", "EMAIL#d", 1.0, 3)
        s.set_email_status("S", "EMAIL#d", "FAILED", 1.0)
    with pytest.raises(ConditionFailed):
        s.claim_email("S", "EMAIL#d", 1.0, 3)


def test_counter_and_prefix_query():
    s = MemoryStore()
    assert [s.incr("C", "AGENT") for _ in range(3)] == [1, 2, 3]
    s.put("P", "ACTIVITY#b", {"x": 2})
    s.put("P", "ACTIVITY#a", {"x": 1})
    s.put("P", "PROFILE", {"y": 1})
    assert [r["x"] for r in s.query_prefix("P", "ACTIVITY#")] == [1, 2]
