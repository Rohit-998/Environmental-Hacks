"""Run chat and translation against the real model, locally, with keys from backend/.env.

    uv run python scripts/chat_smoke.py

Uses the in-memory store and the 19 Nov 2025 replay fixture. Prints answers and whether they passed the
grounding / translation checks. Never prints the API key.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from airday import agent, envfile  # noqa: E402
from airday.store import MemoryStore  # noqa: E402

QUESTIONS = [
    "Can we hold sports day tomorrow afternoon?",
    "Is recess outdoors okay today at 10:30?",
    "Can Class 7 go outside for PE at 08:40 today?",
    "When is the air best today for an outdoor assembly?",
    "Should we cancel the excursion the day after tomorrow morning?",
]
TRANSLATIONS = [
    "Annual day rehearsal moved to Monday at 09:30.",
    "Please send 2 extra masks with your child on Friday.",
    "The bus will leave at 14:15 instead of 13:45 today.",
]


def main() -> None:
    envfile.load()
    os.environ.setdefault("MODEL_PROVIDER", "gemini")
    print(f"provider={os.environ['MODEL_PROVIDER']} model={os.environ.get('MODEL_ID', '(default)')}\n")
    store, ctx, ok = MemoryStore(), dt.date(2025, 11, 19), 0
    for q in QUESTIONS:
        try:
            r = agent.chat(store, "demo", q, [], ctx, "replay")
            ok += r["grounded"]
            print(f"Q: {q}\nA: {r['answer']}\n   ruleIds={r['ruleIds']} grounded={r['grounded']}\n")
        except agent.AgentError as e:
            print(f"Q: {q}\n   ERROR {e.status}: {e.message}\n")
    print(f"chat: {ok}/{len(QUESTIONS)} grounded\n")
    ok = 0
    for t in TRANSLATIONS:
        try:
            r = agent.translate(store, "demo", t)
            ok += r["hiValidated"]
            print(f"EN: {t}\nHI: {r['hi']}\n   validated={r['hiValidated']} {r['problems'] or ''}\n")
        except agent.AgentError as e:
            print(f"EN: {t}\n   ERROR {e.status}: {e.message}\n")
    print(f"translate: {ok}/{len(TRANSLATIONS)} validated")


if __name__ == "__main__":
    main()
