import datetime as dt
import json
import os

import jsonschema
import pytest

from airday import mailer, service
from airday.engine import HourBand, Reading
from airday.rules import load
from airday.store import MemoryStore
from airday.timeutil import IST

SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "brief.schema.json"),
                        encoding="utf-8"))
HERO = dt.date(2025, 11, 19)  # Wednesday; DTU station measured Severe all morning


def test_replay_brief_is_valid_and_labelled():
    s = MemoryStore()
    b = service.build_brief(s, "demo", HERO, mode="replay")
    jsonschema.validate(b, SCHEMA)
    assert b["mode"] == "replay" and b["subject"].startswith("REPLAY · ")
    assert b["generatedAt"].startswith("2025-11-19T06:00")
    assert b["official"]["citySource"] == "bulletin"
    pe = [a for a in b["actions"] if a["kind"] == "activity" and "6B PE" in a["text"]]
    assert pe and pe[0]["ruleIds"] == ["R-SV-PE"]
    assert any(h["escalated"] for h in b["hours"])  # station floor raised the forecast


def test_replay_and_live_keys_are_separate():
    s = MemoryStore()
    b = service.build_brief(s, "demo", HERO, mode="replay")
    service.store_brief(s, "demo", b)
    assert service.get_stored(s, "demo", HERO.isoformat(), "replay") is not None
    assert service.get_stored(s, "demo", HERO.isoformat(), "live") is None


def test_replay_dates_and_fixture_coverage():
    assert "2025-11-19" in service.replay_dates()
    assert service.load_fixture_containing(dt.date(2025, 11, 21))["date"] == "2025-11-19"
    with pytest.raises(KeyError):
        service.load_fixture_containing(dt.date(2024, 1, 1))


def test_evaluate_in_replay_returns_a_rule():
    r = service.evaluate(MemoryStore(), "demo", "pe", dt.date(2025, 11, 20), "14:00", "16:00", mode="replay")
    assert r["ruleId"].startswith("R-") and r["ruleId"].endswith("-PE")


def test_evaluate_matches_the_brief_on_the_replay_day():
    """The chat tool and the 'Check an activity' form must give the same answer as the morning plan."""
    s = MemoryStore()
    brief = service.build_brief(s, "demo", HERO, mode="replay")
    recess = next(a for a in brief["actions"] if a["kind"] == "activity" and "Recess" in a["text"])
    r = service.evaluate(s, "demo", "recess", HERO, "10:30", "10:50", mode="replay")
    assert r["ruleId"] == recess["ruleIds"][0] == "R-SV-REC"


def test_evaluate_uses_forecast_only_for_days_without_station_data():
    r = service.evaluate(MemoryStore(), "demo", "recess", dt.date(2025, 11, 20), "10:30", "10:50", mode="replay")
    assert r["ruleId"] != "R-SV-REC"  # the station floor belongs to 19 Nov, not the next day


def test_station_freshness():
    now = dt.datetime(2025, 11, 19, 9, 30, tzinfo=IST)
    st = [Reading(6, 100, None), Reading(7, 120, None)]
    assert service.latest_fresh_station_hour(st, now) == 7  # hour ended 08:00, 90 min ago
    late = dt.datetime(2025, 11, 19, 11, 30, tzinfo=IST)
    assert service.latest_fresh_station_hour(st, late) is None


def _bands(spec):
    """{hour: band} -> bands dict, for the pure window scan."""
    return {h: HourBand(h, None, None, b, b) for h, b in spec.items()}


def test_scan_windows_finds_clear_runs_and_breaks_on_bad_air():
    rs = load()
    hrs = list(range(8, 15))
    spec = {8: "good", 9: "good", 10: "severe", 11: "severe", 12: "good", 13: "satisfactory", 14: "good"}
    windows = service._scan_windows(rs, _bands(spec), hrs, "pe", 2, 8 * 60, 15 * 60)
    assert [(w["start"], w["end"]) for w in windows] == [("08:00", "10:00"), ("12:00", "15:00")]
    assert all(not rs.rule(w["band"], "pe").change for w in windows)  # only no-change bands are "clear"


def test_scan_windows_respects_the_requested_duration():
    rs = load()
    hrs = list(range(8, 15))
    spec = {8: "good", 9: "good", 10: "severe", 11: "severe", 12: "good", 13: "good", 14: "good"}
    windows = service._scan_windows(rs, _bands(spec), hrs, "pe", 3, 8 * 60, 15 * 60)
    assert [(w["start"], w["end"]) for w in windows] == [("12:00", "15:00")]  # the 2-hour run is too short


def test_safe_windows_severe_replay_day_has_no_pe_window():
    r = service.safe_windows(MemoryStore(), "demo", "pe", HERO, mode="replay")
    assert r["type"] == "pe" and len(r["days"]) == 3
    assert r["days"][0]["date"] == HERO.isoformat()
    assert r["days"][0]["windows"] == []  # 19 Nov read Severe through the morning
    rs = load()
    for day in r["days"]:  # whatever surfaces on the later days must be a genuine no-change window
        for w in day["windows"]:
            assert not rs.rule(w["band"], "pe").change


def test_safe_windows_rejects_a_bad_type():
    with pytest.raises(ValueError):
        service.safe_windows(MemoryStore(), "demo", "lunch", HERO, mode="replay")


def test_live_brief_with_no_forecast_says_unavailable(monkeypatch):
    def boom(*a, **k):
        raise service.sources.UpstreamError("down")

    monkeypatch.setattr(service.sources, "fetch_open_meteo", boom)
    b = service.build_brief(MemoryStore(), "demo", dt.date(2026, 10, 9), mode="live",
                            now=dt.datetime(2026, 10, 9, 6, 0, tzinfo=IST))
    assert b["upstream"]["forecast"] == "unavailable"
    assert "Forecast unavailable" in b["headline"]
    assert all(a["ruleIds"][0].startswith("R-UNK") for a in b["actions"] if a["kind"] == "activity")


def test_diff_reports_changed_actions():
    s = MemoryStore()
    old = service.build_brief(s, "demo", HERO, mode="replay")
    new = json.loads(json.dumps(old))
    new["actions"][0]["ruleIds"] = ["R-P-ASM"]
    d = service.diff(old, new)
    assert len(d) == 1 and d[0]["now"] == ["R-P-ASM"]


# ---------------------------------------------------------------- email protocol

class FakeSES:
    def __init__(self, fail_times=0):
        self.calls, self.fail_times = [], fail_times

    def __call__(self, to, subject, text, html_body):
        self.calls.append(subject)
        if len(self.calls) <= self.fail_times:
            raise RuntimeError("SES throttled")
        return f"msg-{len(self.calls)}"


def _brief():
    return service.build_brief(MemoryStore(), "demo", HERO, mode="replay") | {"mode": "live"}


def test_duplicate_invocation_sends_one_email():
    s, ses, b = MemoryStore(), FakeSES(), _brief()
    assert mailer.send_daily(s, "demo", b, "p@example.com", ses)["sent"]
    assert not mailer.send_daily(s, "demo", b, "p@example.com", ses)["sent"]
    assert len(ses.calls) == 1


def test_failed_send_is_retried_then_sent():
    s, ses, b = MemoryStore(), FakeSES(fail_times=1), _brief()
    with pytest.raises(RuntimeError):
        mailer.send_daily(s, "demo", b, "p@example.com", ses)
    r = mailer.send_daily(s, "demo", b, "p@example.com", ses)
    assert r["sent"] and r["attempts"] == 2
    assert not mailer.send_daily(s, "demo", b, "p@example.com", ses)["sent"]


def test_email_body_has_changes_first_plain_text_and_attribution():
    b = _brief()
    text = mailer.render_text(b)
    assert text.index("WHAT CHANGES TODAY") < text.index("PARENT NOTE")
    assert "[R-SV-PE]" in text and "Open-Meteo" in text
    html_body = mailer.render_html(b)
    assert 'lang="hi"' in html_body and "<script" not in html_body
