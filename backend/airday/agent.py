"""Strands agent: principal chat and free-text Hindi translation (PRD §8).

The model call is injectable (`runner`), so grounding and limits are tested without a model.
Strands is imported lazily, so the rest of the backend works without the `agent` extra.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
from collections.abc import Callable
from typing import Any

from . import service
from . import timeutil as tu
from .store import Store
from .validator import check_chat, check_translation

log = logging.getLogger("airday")

DAILY_CAP = int(os.environ.get("AGENT_DAILY_CAP", "200"))
MAX_TOOL_CALLS = 4
MAX_INPUT = 500
MAX_HISTORY = 6
PLAN_DAYS = 2

CHAT_SYSTEM = """You help a school principal in Delhi plan outdoor school activities around air pollution.
Today is {today} ({weekday}). You can plan from {today} to {last}.
Use the tools. Never guess air quality. To judge an activity, call evaluate_activity; treat events
like sports day or excursions as type "pe". Use 24-hour HH:MM times.
Hourly values are PM2.5 concentrations in µg/m³. Never call an hourly number "AQI".
Do not give medical advice. Keep answers to 2-4 short sentences in plain English.
Reply with JSON only: {{"answer": "<text>", "ruleIds": ["<IDs from evaluate_activity>"]}}
ruleIds must list the rule IDs returned by evaluate_activity that support the answer."""

TRANSLATE_SYSTEM = """Translate the school notice into simple Hindi in Devanagari script for parents.
Keep every number and time exactly as written (you may use Devanagari digits). Output only the translation."""

OUT_OF_RANGE = "I can only plan up to 2 days ahead of {today}, because that's as far as AirDay checks the forecast."
MEDICAL = "I can't give medical advice. Please ask a doctor about a specific child's health."
_MEDICAL_RE = re.compile(r"\b(medicine|medication|dose|inhaler dose|diagnos|prescri|treat(ment)?)\b", re.I)

Runner = Callable[[str, str, list], str]


class AgentError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---------------------------------------------------------------- model

def _model():
    # Gemini is the default only because Bedrock model invocation is blocked on new/free-tier AWS accounts.
    # Set MODEL_PROVIDER=bedrock (and MODEL_ID to a Bedrock model) once access is granted; no code change needed.
    provider = os.environ.get("MODEL_PROVIDER", "gemini")
    if provider == "gemini":
        from strands.models.gemini import GeminiModel

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise AgentError(503, "Assistant unavailable: GEMINI_API_KEY is not configured.")
        # Gemini counts its internal reasoning against max_output_tokens, so the limit is set well above the
        # length of a 2-4 sentence answer.
        # Bounded so a busy or rate-limited model fails inside the 25 s Lambda timeout (HTTP API limit is 30 s).
        http = {"timeout": 15_000, "retry_options": {"attempts": 2}}
        return GeminiModel(client_args={"api_key": key, "http_options": http},
                           model_id=os.environ.get("MODEL_ID", "gemini-3.5-flash"),
                           params={"temperature": 0.2, "max_output_tokens": 4096})
    model_id = os.environ.get("MODEL_ID", "global.amazon.nova-2-lite-v1:0")
    if provider == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(model_id=model_id, region_name=os.environ.get("BEDROCK_REGION", "ap-south-1"),
                            temperature=0.2, max_tokens=600)
    if provider == "litellm":
        from strands.models.litellm import LiteLLMModel

        return LiteLLMModel(model_id=model_id, params={"temperature": 0.2, "max_tokens": 600})
    raise AgentError(503, f"unknown MODEL_PROVIDER {provider!r}")


def _is_rate_limit(e: Exception) -> bool:
    text = str(e).lower()
    return "429" in text or "quota" in text or "resource_exhausted" in text or "throttl" in text


def strands_runner(system: str, prompt: str, tools: list) -> str:
    from strands import Agent

    agent = Agent(model=_model(), system_prompt=system, tools=tools, callback_handler=None)
    return str(agent(prompt))


# ---------------------------------------------------------------- tools

class ToolBox:
    """Read-only tools for one chat turn. Records every rule ID returned, and caps tool calls."""

    def __init__(self, store: Store, school_id: str, context: dt.date, mode: str):
        self.store, self.school_id, self.context, self.mode = store, school_id, context, mode
        self.calls = 0
        self.rule_ids: set[str] = set()
        self.evaluated = False

    def _tick(self) -> None:
        self.calls += 1
        if self.calls > MAX_TOOL_CALLS:
            raise AgentError(429, "too many tool calls in one question")

    def _in_range(self, date: str) -> dt.date:
        d = dt.date.fromisoformat(date)
        if not (self.context <= d <= self.context + dt.timedelta(days=PLAN_DAYS)):
            raise ValueError(f"{date} is outside {self.context}..{self.context + dt.timedelta(days=PLAN_DAYS)}")
        return d

    def get_day(self, date: str) -> dict:
        """Hourly PM2.5 forecast (µg/m³) and bands for school hours on a date (YYYY-MM-DD)."""
        self._tick()
        d = self._in_range(date)
        out = service.evaluate(self.store, self.school_id, "pe", d, "07:00", "15:00", mode=self.mode)
        return {"date": date, "hours": out["hours"]}

    def evaluate_activity(self, type: str, date: str, start: str, end: str) -> dict:  # noqa: A002
        """Check an activity. type: assembly, recess or pe. date: YYYY-MM-DD. start/end: HH:MM.
        Returns the band and the rule ID with the recommended action."""
        self._tick()
        d = self._in_range(date)
        r = service.evaluate(self.store, self.school_id, type, d, start, end, mode=self.mode)
        self.evaluated = True
        self.rule_ids.add(r["ruleId"])
        return {k: r[k] for k in ("type", "date", "start", "end", "bandName", "ruleId", "text", "hours")}

    def strands_tools(self) -> list:
        from strands import tool

        return [tool(self.get_day), tool(self.evaluate_activity)]


# ---------------------------------------------------------------- chat

def _parse(text: str) -> Any:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _check_cap(store: Store, school_id: str) -> None:
    """Per-tenant daily cap, so one school (or the public demo) can't drain the model budget for others."""
    n = store.incr(f"COUNTER#{tu.now_ist().date().isoformat()}", f"AGENT#{school_id}", ttl=7 * 86400)
    if n > DAILY_CAP:
        raise AgentError(429, "Chat limit reached for today.")


def chat(store: Store, school_id: str, message: str, history: list[dict], context: dt.date, mode: str,
         runner: Runner | None = None, tools_factory: Callable[[ToolBox], list] | None = None) -> dict:
    message = (message or "").strip()
    if not message:
        raise AgentError(400, "message is empty")
    if len(message) > MAX_INPUT:
        raise AgentError(400, f"message is over {MAX_INPUT} characters")
    if _MEDICAL_RE.search(message):
        return {"answer": MEDICAL, "ruleIds": [], "grounded": True, "fixed": True}
    _check_cap(store, school_id)

    last = context + dt.timedelta(days=PLAN_DAYS)
    system = CHAT_SYSTEM.format(today=context.isoformat(), weekday=tu.weekday(context), last=last.isoformat())
    convo = "\n".join(f"{m.get('role', 'user')}: {str(m.get('content', ''))[:MAX_INPUT]}"
                      for m in (history or [])[-MAX_HISTORY:])
    prompt = (convo + "\n" if convo else "") + f"user: {message}"

    box = ToolBox(store, school_id, context, mode)
    runner = runner or strands_runner
    tools = (tools_factory or (lambda b: b.strands_tools()))(box)

    for attempt in range(2):
        try:
            raw = runner(system, prompt, tools)
        except ValueError as e:  # a tool rejected an out-of-range date
            return {"answer": OUT_OF_RANGE.format(today=context.isoformat()), "ruleIds": [], "grounded": True,
                    "fixed": True, "detail": str(e)}
        except AgentError:
            raise
        except Exception as e:  # model or provider failure: chat degrades, the morning plan is unaffected
            log.error("model call failed: %s", e)
            if _is_rate_limit(e):
                raise AgentError(429, "The assistant is busy. Try again in a minute.") from None
            raise AgentError(503, "Assistant unavailable right now. The daily plan still works.") from None
        out = _parse(raw)
        problems = check_chat(out, box.rule_ids, box.evaluated) if out is not None else ["output is not JSON"]
        if not problems:
            return {"answer": out["answer"], "ruleIds": out.get("ruleIds") or [], "grounded": True}
        log.warning("chat answer rejected (attempt %d): %s", attempt + 1, problems)
        prompt += ("\nsystem: Your last reply was rejected: " + "; ".join(problems) +
                   ". Reply again with JSON only, citing rule IDs returned by evaluate_activity.")
    return {
        "answer": "I couldn't give a grounded answer. Here is the raw evaluation from the rules.",
        "ruleIds": sorted(box.rule_ids), "grounded": False,
    }


def translate(store: Store, school_id: str, text: str, runner: Runner | None = None) -> dict:
    text = (text or "").strip()
    if not text:
        raise AgentError(400, "text is empty")
    if len(text) > 300:
        raise AgentError(400, "text is over 300 characters")
    _check_cap(store, school_id)
    try:
        hi = (runner or strands_runner)(TRANSLATE_SYSTEM, text, []).strip()
    except Exception as e:
        log.error("model call failed: %s", e)
        if _is_rate_limit(e):
            raise AgentError(429, "Translation is busy. Try again in a minute.") from None
        raise AgentError(503, "Translation unavailable right now. The line stays in English.") from None
    problems = check_translation(text, hi)
    return {"en": text, "hi": hi if not problems else None, "hiValidated": not problems, "problems": problems}


# ---------------------------------------------------------------- routes (used by api.route)

def _post_chat(store, p, q, body, headers):
    from .api import HttpError, _json, require_school

    sid = require_school(p)
    data = _json(body)
    mode = data.get("mode", "live")
    try:
        context = dt.date.fromisoformat(data["date"]) if data.get("date") else tu.now_ist().date()
    except ValueError:
        raise HttpError(400, "date must be YYYY-MM-DD") from None
    try:
        return 200, chat(store, sid, data.get("message", ""), data.get("history") or [], context, mode)
    except AgentError as e:
        raise HttpError(e.status, e.message) from None
    except ImportError:
        raise HttpError(503, "Assistant unavailable.") from None


def _post_translate(store, p, q, body, headers):
    from .api import HttpError, _json, require_school, require_write

    require_write(p)
    sid = require_school(p)
    try:
        return 200, translate(store, sid, _json(body).get("text", ""))
    except AgentError as e:
        raise HttpError(e.status, e.message) from None
    except ImportError:
        raise HttpError(503, "Assistant unavailable.") from None


ROUTES = {("POST", "/chat"): _post_chat, ("POST", "/note/translate"): _post_translate}
