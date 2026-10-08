import datetime as dt
import json

import pytest

from airday import agent
from airday.store import MemoryStore

CTX = dt.date(2025, 11, 19)


def fake(script):
    """A runner that calls tools as scripted, then returns the scripted reply."""
    replies = iter(script)

    def run(system, prompt, tools):
        step = next(replies)
        for name, args in step.get("calls", []):
            tools[name](**args)
        return step["reply"]

    return run


def tools_by_name(box):
    return {"get_day": box.get_day, "evaluate_activity": box.evaluate_activity}


EVAL = ("evaluate_activity", {"type": "pe", "date": "2025-11-20", "start": "14:00", "end": "16:00"})


def ask(script, message="Can we hold sports day tomorrow afternoon?", store=None):
    return agent.chat(store or MemoryStore(), message, [], CTX, "replay",
                      runner=fake(script), tools_factory=tools_by_name)


def test_grounded_answer_passes():
    box_rule = []

    def run(system, prompt, tools):
        r = tools["evaluate_activity"](**EVAL[1])
        box_rule.append(r["ruleId"])
        return json.dumps({"answer": "Yes.", "ruleIds": [r["ruleId"]]})

    out = agent.chat(MemoryStore(), "sports day tomorrow?", [], CTX, "replay", runner=run, tools_factory=tools_by_name)
    assert out["grounded"] and out["ruleIds"] == box_rule


def test_uncited_answer_is_retried_then_falls_back_to_raw_rules():
    out = ask([
        {"calls": [EVAL], "reply": '{"answer": "Sure!", "ruleIds": []}'},
        {"calls": [], "reply": '{"answer": "Sure!", "ruleIds": ["R-G-PE-FAKE"]}'},
    ])
    assert not out["grounded"] and out["ruleIds"]


def test_out_of_range_date_gets_fixed_reply():
    far = ("evaluate_activity", {"type": "pe", "date": "2025-11-25", "start": "14:00", "end": "16:00"})
    out = ask([{"calls": [far], "reply": "{}"}])
    assert out["fixed"] and "2 days ahead" in out["answer"]


def test_medical_question_never_reaches_the_model():
    out = ask([], message="What inhaler dose should a child take?")
    assert out["fixed"] and "doctor" in out["answer"]


def test_input_limits_and_daily_cap(monkeypatch):
    with pytest.raises(agent.AgentError):
        ask([], message="x" * 501)
    monkeypatch.setattr(agent, "DAILY_CAP", 1)
    s = MemoryStore()
    ask([{"calls": [], "reply": '{"answer": "Hi", "ruleIds": []}'}], message="hello", store=s)
    with pytest.raises(agent.AgentError) as e:
        ask([{"calls": [], "reply": "{}"}], message="hello", store=s)
    assert e.value.status == 429


def test_tool_call_cap():
    calls = [EVAL] * 5
    with pytest.raises(agent.AgentError):
        ask([{"calls": calls, "reply": "{}"}])


def test_translate_validates_output():
    good = agent.translate(MemoryStore(), "Rehearsal on Monday at 09:30.",
                           runner=lambda s, p, t: "अभ्यास सोमवार को ०९:३० बजे होगा।")
    assert good["hiValidated"] and good["hi"]
    bad = agent.translate(MemoryStore(), "Rehearsal on Monday at 09:30.",
                          runner=lambda s, p, t: "अभ्यास सोमवार को होगा।")
    assert not bad["hiValidated"] and bad["hi"] is None
