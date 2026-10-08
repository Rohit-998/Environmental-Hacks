"""A model or provider failure must surface as a clean 503, never a 500."""
import datetime as dt

import pytest

from airday import agent, api
from airday.store import MemoryStore


def boom(system, prompt, tools):
    raise RuntimeError("ValidationException: Operation not allowed")


def test_chat_model_failure_is_a_503_agent_error():
    with pytest.raises(agent.AgentError) as e:
        agent.chat(MemoryStore(), "demo", "Is PE okay today?", [], dt.date(2025, 11, 19), "replay",
                   runner=boom, tools_factory=lambda b: {})
    assert e.value.status == 503 and "unavailable" in e.value.message.lower()


def test_translate_model_failure_is_a_503_agent_error():
    with pytest.raises(agent.AgentError) as e:
        agent.translate(MemoryStore(), "demo", "Rehearsal on Monday at 09:30.", runner=boom)
    assert e.value.status == 503


def quota(system, prompt, tools):
    raise RuntimeError("429 RESOURCE_EXHAUSTED. You exceeded your current quota")


def test_rate_limit_is_a_429_not_a_503():
    with pytest.raises(agent.AgentError) as e:
        agent.chat(MemoryStore(), "demo", "Is PE okay today?", [], dt.date(2025, 11, 19), "replay",
                   runner=quota, tools_factory=lambda b: {})
    assert e.value.status == 429
    with pytest.raises(agent.AgentError) as e:
        agent.translate(MemoryStore(), "demo", "Rehearsal on Monday at 09:30.", runner=quota)
    assert e.value.status == 429


def test_gemini_is_the_default_provider_and_needs_a_key(monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(agent.AgentError) as e:
        agent._model()
    assert e.value.status == 503 and "GEMINI_API_KEY" in e.value.message


def test_model_ids_primary_then_fallbacks(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("MODEL_ID", "a")
    monkeypatch.setenv("MODEL_FALLBACKS", "b, a ,c")
    assert agent.model_ids() == ["a", "b", "c"]
    monkeypatch.setenv("MODEL_PROVIDER", "bedrock")
    monkeypatch.setenv("MODEL_ID", "nova")
    assert agent.model_ids() == ["nova"]


class FakeAgent:
    """Stands in for strands.Agent: fails for the models listed in `fail`, answers for the rest."""
    calls: list[str] = []
    fail: dict[str, str] = {}

    def __init__(self, model, **kw):
        self.model_id = model

    def __call__(self, prompt):
        FakeAgent.calls.append(self.model_id)
        if self.model_id in FakeAgent.fail:
            raise RuntimeError(FakeAgent.fail[self.model_id])
        return '{"answer": "ok", "ruleIds": []}'


@pytest.fixture
def fake_strands(monkeypatch):
    import sys
    import types

    mod = types.ModuleType("strands")
    mod.Agent = FakeAgent
    monkeypatch.setitem(sys.modules, "strands", mod)
    monkeypatch.setattr(agent, "_model", lambda model_id=None: model_id)
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("MODEL_ID", "primary")
    monkeypatch.setenv("MODEL_FALLBACKS", "second,third")
    FakeAgent.calls, FakeAgent.fail = [], {}
    return FakeAgent


def test_runner_falls_back_on_rate_limit_and_overload(fake_strands):
    fake_strands.fail = {"primary": "429 RESOURCE_EXHAUSTED quota", "second": "503 UNAVAILABLE high demand"}
    assert agent.strands_runner("s", "p", []) == '{"answer": "ok", "ruleIds": []}'
    assert fake_strands.calls == ["primary", "second", "third"]


def test_runner_does_not_fall_back_on_other_errors(fake_strands):
    fake_strands.fail = {"primary": "400 INVALID_ARGUMENT bad request"}
    with pytest.raises(RuntimeError):
        agent.strands_runner("s", "p", [])
    assert fake_strands.calls == ["primary"]


def test_runner_raises_last_error_when_every_model_is_busy(fake_strands):
    fake_strands.fail = {m: "429 quota" for m in ("primary", "second", "third")}
    with pytest.raises(RuntimeError, match="429"):
        agent.strands_runner("s", "p", [])


def test_chat_route_returns_503_when_the_model_fails(monkeypatch):
    monkeypatch.setattr(agent, "strands_runner", boom)
    monkeypatch.setattr(agent.ToolBox, "strands_tools", lambda self: [])
    status, body = api.route("POST", "/chat", {}, '{"message": "Is PE okay?", "date": "2025-11-19", "mode": "replay"}',
                             {"content-type": "application/json"}, MemoryStore(), extra=agent.ROUTES)
    assert status == 503 and "unavailable" in body["error"].lower()
