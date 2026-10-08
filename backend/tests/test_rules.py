import os
import re

import pytest

from airday.rules import SCOPES, UNKNOWN, load

RS = load()
SOURCES = os.path.join(os.path.dirname(__file__), "..", "rules", "SOURCES.md")


def test_every_band_scope_cell_has_exactly_one_rule():
    bands = RS.order + [UNKNOWN]
    for b in bands:
        for s in SCOPES:
            assert (b, s) in RS.by_cell, f"missing rule for {b} x {s}"
    assert len(RS.rules) == len(bands) * len(SCOPES) == 35


def test_rule_ids_follow_the_naming_pattern():
    for r in RS.rules.values():
        assert re.fullmatch(r"R-(G|S|MOD|P|VP|SV|UNK)-(ASM|REC|PE|WIN|NOTE)", r.id), r.id


def test_emitted_notes_have_english_and_hindi():
    for r in RS.rules.values():
        if r.scope == "note" and r.emit:
            assert r.en and r.hi, r.id
            assert "{hours}" in r.en and "{hours}" in r.hi, r.id


def test_windows_have_an_instruction():
    for r in RS.rules.values():
        if r.scope == "window":
            assert r.instruction in ("open", "closed"), r.id


def _sources():
    text = open(SOURCES, encoding="utf-8").read()
    out = {}
    for block in text.split("\n## ")[1:]:
        key = block.split("\n", 1)[0].strip()
        status = re.search(r"- status:\s*(\w+)", block)
        out[key] = status.group(1) if status else None
    return out


def test_every_source_key_is_listed_in_sources_md():
    keys = _sources()
    for r in RS.rules.values():
        assert r.source in keys, f"{r.id} cites {r.source}, missing from SOURCES.md"


@pytest.mark.skipif(not os.environ.get("RELEASE"), reason="release check, run with RELEASE=1")
def test_release_no_emitted_rule_cites_an_unread_source():
    keys = _sources()
    pending = sorted({r.source for r in RS.rules.values() if r.emit and keys[r.source] != "read"})
    assert not pending, f"sources still pending: {pending}"
