"""Output validator. Runs at runtime before any email is sent, and in tests.

A brief that fails is never emailed.
"""
from __future__ import annotations

import re
from typing import Any

from .rules import RuleSet

# "AQI" next to a number in hourly text is banned: hourly values are concentrations, not AQI.
_AQI_NEAR_NUMBER = re.compile(r"\bAQI\b[^.\n]{0,12}\d|\d[^.\n]{0,12}\bAQI\b")


class BriefInvalid(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def check_brief(rs: RuleSet, brief: dict[str, Any], activity_ids: list[str]) -> list[str]:
    problems: list[str] = []
    seen_activities: dict[str, int] = {}
    notes = 0
    for i, a in enumerate(brief.get("actions", [])):
        ids = a.get("ruleIds") or []
        if not ids:
            problems.append(f"action {i} has no rule ID")
        for rid in ids:
            if rid not in rs.rules:
                problems.append(f"action {i} cites unknown rule {rid}")
        if a.get("kind") == "activity":
            aid = a.get("activityId")
            seen_activities[aid] = seen_activities.get(aid, 0) + 1
        if a.get("kind") == "note":
            notes += 1
        for field in ("text",):
            if _AQI_NEAR_NUMBER.search(a.get(field) or ""):
                problems.append(f"action {i} labels an hourly number as AQI")
    for aid in activity_ids:
        n = seen_activities.get(aid, 0)
        if n != 1:
            problems.append(f"activity {aid} has {n} actions, expected 1")
    for aid in seen_activities:
        if aid not in activity_ids:
            problems.append(f"action for activity {aid} not in today's timetable")
    if notes != 1:
        problems.append(f"expected 1 parent-note action, found {notes}")
    if _AQI_NEAR_NUMBER.search(brief.get("headline") or ""):
        problems.append("headline labels an hourly number as AQI")
    note = brief.get("parentNote") or {}
    if note.get("ruleId") not in rs.rules:
        problems.append("parent note cites an unknown rule")
    return problems


def assert_valid(rs: RuleSet, brief: dict[str, Any], activity_ids: list[str]) -> None:
    problems = check_brief(rs, brief, activity_ids)
    if problems:
        raise BriefInvalid(problems)


# ---------------------------------------------------------------- chat grounding

def check_chat(answer: dict[str, Any], tool_rule_ids: set[str], evaluated: bool) -> list[str]:
    """Chat output must be {answer, ruleIds}. If an activity was evaluated, at least one rule ID
    must be cited, and every cited ID must have come from a tool in this turn."""
    problems = []
    if not isinstance(answer, dict) or not isinstance(answer.get("answer"), str):
        return ["output is not {answer, ruleIds}"]
    ids = answer.get("ruleIds") or []
    if not isinstance(ids, list):
        return ["ruleIds is not a list"]
    if evaluated and not ids:
        problems.append("an activity was evaluated but no rule ID was cited")
    foreign = [r for r in ids if r not in tool_rule_ids]
    if foreign:
        problems.append(f"cites rule IDs no tool returned: {foreign}")
    return problems


# ---------------------------------------------------------------- translation

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUM = re.compile(r"\d+(?::\d{2})?")


def check_translation(en: str, hi: str, max_len: int = 300) -> list[str]:
    problems = []
    if not hi.strip():
        return ["translation is empty"]
    if len(en) > max_len:
        problems.append(f"English text is over {max_len} characters")
    norm = hi.translate(_DEVANAGARI_DIGITS)
    for tok in _NUM.findall(en):
        variants = {tok, tok.lstrip("0") or "0"}
        if ":" in tok:
            h, m = tok.split(":")
            variants.add(f"{int(h)}:{m}")
        if not any(v in norm for v in variants):
            problems.append(f"number or time {tok} missing from translation")
    letters = [c for c in hi if c.isalpha()]
    if letters:
        deva = sum(1 for c in letters if "ऀ" <= c <= "ॿ")
        if deva / len(letters) < 0.6:
            problems.append("translation is not mostly Devanagari")
    else:
        problems.append("translation has no letters")
    ratio = len(hi) / max(len(en), 1)
    if not (0.5 <= ratio <= 2.5):
        problems.append(f"translation length ratio {ratio:.2f} outside 0.5–2.5")
    return problems
