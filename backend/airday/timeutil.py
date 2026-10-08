"""IST helpers. Everything in AirDay is Asia/Kolkata (UTC+5:30, no DST)."""
from __future__ import annotations

import datetime as dt

IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def parse_hhmm(s: str) -> int:
    """'08:40' -> minutes since midnight. Raises ValueError on bad input."""
    s = s.strip()
    hh, mm = s.split(":")
    if len(mm) != 2 or not hh.isdigit() or not mm.isdigit():
        raise ValueError(f"bad time {s!r}")
    h, m = int(hh), int(mm)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"bad time {s!r}")
    return h * 60 + m


def fmt_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hours_overlapped(start_min: int, end_min: int) -> list[int]:
    """Hours h whose [h:00, h+1:00) overlaps [start, end). 08:40-09:20 -> [8, 9]; 08:00-09:00 -> [8]."""
    if end_min <= start_min:
        return []
    return list(range(start_min // 60, (end_min - 1) // 60 + 1))


def weekday(date: dt.date) -> str:
    return DAYS[date.weekday()]


def to_ist(ts: str) -> dt.datetime:
    """Parse an ISO timestamp (with Z or offset) into IST."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    d = dt.datetime.fromisoformat(ts)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(IST)


def ranges(hours: list[int]) -> list[tuple[int, int]]:
    """[8,9,10,13] -> [(8,11),(13,14)] as hour ranges [start, end)."""
    out: list[tuple[int, int]] = []
    for h in sorted(set(hours)):
        if out and out[-1][1] == h:
            out[-1] = (out[-1][0], h + 1)
        else:
            out.append((h, h + 1))
    return out


def fmt_ranges(hours: list[int]) -> str:
    return ", ".join(f"{a:02d}:00–{b:02d}:00" for a, b in ranges(hours))
