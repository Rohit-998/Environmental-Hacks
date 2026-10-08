"""Loads rules.yaml and answers band and rule lookups. No I/O beyond reading the file once."""
from __future__ import annotations

import functools
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

RULES_PATH = os.environ.get(
    "AIRDAY_RULES", os.path.join(os.path.dirname(__file__), "..", "rules", "rules.yaml")
)

UNKNOWN = "unknown"
ACTIVITY_SCOPES = ("assembly", "recess", "pe")
SCOPES = ACTIVITY_SCOPES + ("window", "note")


@dataclass(frozen=True)
class Rule:
    id: str
    band: str
    scope: str
    change: bool
    en: str
    basis: str
    source: str
    hi: str = ""
    emit: bool = True
    optional: bool = False
    instruction: str | None = None


@dataclass
class RuleSet:
    version: str
    order: list[str]
    names: dict[str, str]
    hindi: dict[str, str]
    pm25_upper: dict[str, float]
    pm10_upper: dict[str, float]
    valid_max: float
    rules: dict[str, Rule] = field(default_factory=dict)
    by_cell: dict[tuple[str, str], Rule] = field(default_factory=dict)

    # ---------- bands

    def rank(self, band: str) -> int:
        """Good=0 ... Severe=5. Unknown has no rank and must be handled by the caller."""
        return self.order.index(band)

    def _band_for(self, value: float | None, uppers: dict[str, float]) -> str | None:
        if value is None:
            return None
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        if v < 0 or v > self.valid_max:
            return None
        for band in self.order[:-1]:
            if v <= uppers[band]:
                return band
        return self.order[-1]

    def band_of(self, pm25: float | None, pm10: float | None) -> str:
        """Worse of the PM2.5 and PM10 bands. Missing or out-of-range values are ignored."""
        found = [b for b in (self._band_for(pm25, self.pm25_upper), self._band_for(pm10, self.pm10_upper)) if b]
        if not found:
            return UNKNOWN
        return max(found, key=self.rank)

    def worse(self, a: str, b: str) -> str:
        """Worse of two known bands."""
        return a if self.rank(a) >= self.rank(b) else b

    def name(self, band: str) -> str:
        return self.names[band]

    # ---------- rules

    def rule(self, band: str, scope: str) -> Rule:
        return self.by_cell[(band, scope)]


def _load(path: str) -> RuleSet:
    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)
    b = raw["bands"]
    rs = RuleSet(
        version=str(raw["version"]),
        order=list(b["order"]),
        names=dict(b["names"]),
        hindi=dict(b["hindi"]),
        pm25_upper={k: float(v) for k, v in b["pm25_upper"].items()},
        pm10_upper={k: float(v) for k, v in b["pm10_upper"].items()},
        valid_max=float(b["valid_max"]),
    )
    for item in raw["rules"]:
        r = Rule(
            id=item["id"],
            band=item["band"],
            scope=item["scope"],
            change=bool(item["change"]),
            en=item.get("en", ""),
            hi=item.get("hi", ""),
            basis=item["basis"],
            source=item["source"],
            emit=bool(item.get("emit", True)),
            optional=bool(item.get("optional", False)),
            instruction=item.get("instruction"),
        )
        if r.id in rs.rules:
            raise ValueError(f"duplicate rule id {r.id}")
        if (r.band, r.scope) in rs.by_cell:
            raise ValueError(f"two rules for {r.band} x {r.scope}")
        rs.rules[r.id] = r
        rs.by_cell[(r.band, r.scope)] = r
    return rs


@functools.lru_cache(maxsize=4)
def load(path: str = RULES_PATH) -> RuleSet:
    return _load(os.path.abspath(path))
