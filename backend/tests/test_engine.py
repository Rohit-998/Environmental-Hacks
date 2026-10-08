from airday.engine import Activity, Reading, activity_band, build_plan, hourly_bands
from airday.rules import UNKNOWN, load

RS = load()


def fc(values: dict[int, float | None]) -> list[Reading]:
    return [Reading(h, v, None) for h, v in values.items()]


def plan_for(pm25_by_hour, activities, station=None, station_hour=None):
    bands = hourly_bands(RS, fc(pm25_by_hour), station, station_hour)
    return build_plan(RS, "2025-11-20", "07:45", "14:00", activities, bands), bands


ACTS = [
    Activity("a1", "Thu", "07:50", "08:10", "assembly", "Morning assembly"),
    Activity("a2", "Thu", "08:40", "09:20", "pe", "Class 6B PE"),
    Activity("a3", "Thu", "10:30", "10:50", "recess", "Recess"),
    Activity("a4", "Thu", "13:00", "13:40", "pe", "Class 8A PE"),
]
VP_MORNING = {7: 140, 8: 140, 9: 130, 10: 125, 11: 100, 12: 85, 13: 80}


def by_activity(plan):
    return {a.activity_id: a for a in plan.actions if a.kind == "activity"}


def test_one_action_per_activity_with_expected_rules():
    plan, _ = plan_for(VP_MORNING, ACTS)
    acts = by_activity(plan)
    assert set(acts) == {"a1", "a2", "a3", "a4"}
    assert acts["a1"].rule_ids == ["R-VP-ASM"]
    assert acts["a2"].rule_ids == ["R-VP-PE"]
    assert acts["a3"].rule_ids == ["R-VP-REC"]
    assert acts["a4"].rule_ids == ["R-MOD-PE"]
    assert acts["a2"].change and not acts["a4"].change


def test_activity_spanning_two_hours_takes_the_worse_band():
    plan, _ = plan_for({8: 70, 9: 130}, [Activity("x", "Thu", "08:40", "09:20", "pe", "PE")])
    assert by_activity(plan)["x"].rule_ids == ["R-VP-PE"]


def test_activity_ending_on_the_hour_does_not_touch_next_hour():
    plan, _ = plan_for({8: 70, 9: 300}, [Activity("x", "Thu", "08:00", "09:00", "pe", "PE")])
    assert by_activity(plan)["x"].rule_ids == ["R-MOD-PE"]


def test_unknown_plus_moderate_is_unknown_but_unknown_plus_very_poor_stays_very_poor():
    bands = hourly_bands(RS, fc({8: 70, 9: None}))
    assert activity_band(RS, bands, [8, 9]) == UNKNOWN
    bands = hourly_bands(RS, fc({8: 130, 9: None}))
    assert activity_band(RS, bands, [8, 9]) == "very_poor"
    assert activity_band(RS, bands, [12]) == UNKNOWN


def test_window_runs_merge_by_instruction():
    plan, _ = plan_for({7: 100, 8: 130, 9: 130, 10: 80, 11: 80, 12: 80, 13: 80}, [])
    wins = [a for a in plan.actions if a.kind == "window"]
    assert [w.text for w in wins] == [
        "Windows 07:45–10:00: keep closed.",
        "Windows 10:00–14:00: open as normal.",
    ]
    assert wins[0].rule_ids == ["R-P-WIN", "R-VP-WIN"]
    assert wins[0].band == "very_poor"


def test_one_parent_note_from_worst_band():
    plan, _ = plan_for(VP_MORNING, ACTS)
    notes = [a for a in plan.actions if a.kind == "note"]
    assert len(notes) == 1 and notes[0].rule_ids == ["R-VP-NOTE"]
    assert "07:00–11:00" in plan.note_en and "07:00–11:00" in plan.note_hi


def test_clean_day_has_no_parent_note():
    plan, _ = plan_for({h: 20 for h in range(7, 14)}, ACTS)
    assert plan.note_rule_id == "R-G-NOTE" and plan.note_en == ""
    assert not any(a.change for a in plan.actions)


def test_all_unknown_day_sends_no_note():
    plan, _ = plan_for({h: None for h in range(7, 14)}, ACTS)
    assert plan.note_rule_id == "R-UNK-NOTE" and plan.note_en == ""
    assert all(a.rule_ids[0].startswith("R-UNK") for a in plan.actions if a.kind == "activity")


def test_escalation_raises_three_hours_and_never_lowers():
    station = [Reading(8, 160, None)]
    bands = hourly_bands(RS, fc({8: 70, 9: 70, 10: 70, 11: 70}), station, station_hour=8)
    assert [bands[h].band for h in (8, 9, 10, 11)] == ["very_poor"] * 3 + ["moderate"]
    assert bands[8].escalated and not bands[11].escalated

    station = [Reading(8, 20, None)]
    bands = hourly_bands(RS, fc({8: 130}), station, station_hour=8)
    assert bands[8].band == "very_poor" and not bands[8].escalated


def test_floor_for_the_rest_of_the_day_stops_at_hour_23():
    station = [Reading(5, 300, None)]
    bands = hourly_bands(RS, fc({h: 70 for h in range(24)}), station, station_hour=5, escalation_hours=24)
    assert max(bands) == 23
    assert all(bands[h].band == "severe" for h in range(5, 24))
    assert bands[4].band == "moderate"


def test_escalation_fills_unknown_hours_and_stale_reading_is_ignored():
    station = [Reading(8, 100, None)]
    bands = hourly_bands(RS, fc({8: None, 9: None}), station, station_hour=8)
    assert bands[8].band == "poor" and bands[9].band == "poor"
    bands = hourly_bands(RS, fc({8: None}), station, station_hour=None)
    assert bands[8].band == UNKNOWN
