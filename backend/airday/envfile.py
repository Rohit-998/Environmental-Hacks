"""Minimal .env reader for local tools (dev server, deploy script). Standard library only.

Lines are KEY=VALUE; blank lines and lines starting with # are ignored; values may be quoted. Comments must be on
their own line. Empty values are skipped, and existing environment variables win unless override=True.
"""
from __future__ import annotations

import os

BACKEND_ENV = os.path.join(os.path.dirname(__file__), "..", ".env")


def parse(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, sep, val = line.partition("=")
            if not sep:
                continue
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            values[key.strip()] = val
    return values


def load(path: str = BACKEND_ENV, override: bool = False) -> dict[str, str]:
    values = parse(path)
    for k, v in values.items():
        if v and (override or k not in os.environ):
            os.environ[k] = v
    return values


def set_value(path: str, key: str, value: str) -> None:
    """Set KEY=value in the file, replacing an existing line or appending one."""
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
