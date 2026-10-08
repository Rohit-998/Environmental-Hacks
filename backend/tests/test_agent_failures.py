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


def test_chat_route_returns_503_when_the_model_fails(monkeypatch):
    monkeypatch.setattr(agent, "strands_runner", boom)
    monkeypatch.setattr(agent.ToolBox, "strands_tools", lambda self: [])
    status, body = api.route("POST", "/chat", {}, '{"message": "Is PE okay?", "date": "2025-11-19", "mode": "replay"}',
                             {"content-type": "application/json"}, MemoryStore(), extra=agent.ROUTES)
    assert status == 503 and "unavailable" in body["error"].lower()
