"""Email rendering and the at-most-once send protocol (PRD §9.2)."""
from __future__ import annotations

import html
import logging
import os
import time
from typing import Any, Callable

from .store import ConditionFailed, Store, school_pk

log = logging.getLogger("airday")

MAX_ATTEMPTS = 3
ATTRIBUTION = ("Forecast: CAMS via Open-Meteo (city-area, ~40 km). Station data: OpenAQ / CPCB. "
               "Official AQI: CPCB via data.gov.in. General guidance, not medical advice.")

BAND_COLOURS = {
    "good": "#1b7f3b", "satisfactory": "#4d7c0f", "moderate": "#8a6d00",
    "poor": "#b45309", "very_poor": "#b91c1c", "severe": "#7e1d5f", "unknown": "#4b5563",
}


def render_text(brief: dict, dashboard_url: str = "") -> str:
    o, g = brief["official"], brief["grap"]
    lines = [brief["subject"], ""]
    if brief["mode"] == "replay":
        lines += [f"REPLAY of {brief['date']} using archived data.", ""]
    lines.append(_official_line(o))
    lines.append(g["label"])
    lines.append(brief["headline"])
    lines.append("")
    changes = [a for a in brief["actions"] if a["change"] and a["kind"] != "note"]
    same = [a for a in brief["actions"] if not a["change"] and a["kind"] != "note"]
    lines.append("WHAT CHANGES TODAY" if changes else "NO CHANGES TODAY")
    for a in changes:
        lines.append(f"- {a['text']} [{', '.join(a['ruleIds'])}]")
    if same:
        lines += ["", "AS NORMAL"]
        for a in same:
            lines.append(f"- {a['text']} [{', '.join(a['ruleIds'])}]")
    pn = brief["parentNote"]
    lines.append("")
    if pn["send"]:
        lines.append("PARENT NOTE" + (" (optional)" if pn["optional"] else " (recommended)"))
        lines += [pn["en"], "", pn["hi"]]
    else:
        lines.append("No parent note needed today.")
    if dashboard_url:
        lines += ["", f"Dashboard: {dashboard_url}"]
    lines += ["", f"As of {brief['generatedAt'][11:16]} IST. {ATTRIBUTION}"]
    return "\n".join(lines)


def _official_line(o: dict) -> str:
    parts = []
    if o.get("stationAqi") is not None:
        parts.append(f"Official CPCB AQI, {o.get('stationName') or 'station'} (24-hr rolling"
                     f"{', as of ' + o['stationAsOf'] if o.get('stationAsOf') else ''}): "
                     f"{o['stationAqi']} {o.get('stationBandName') or ''}".strip())
    if o.get("cityAqi") is not None:
        src = "CPCB bulletin" if o.get("citySource") == "bulletin" else "average of Delhi stations"
        parts.append(f"Delhi AQI ({src}{', ' + o['cityAsOf'] if o.get('cityAsOf') else ''}): "
                     f"{o['cityAqi']} {o.get('cityBandName') or ''}".strip())
    return " · ".join(parts) if parts else "Official AQI unavailable right now."


def render_html(brief: dict, dashboard_url: str = "") -> str:
    e = html.escape
    o, g = brief["official"], brief["grap"]

    def row(a: dict) -> str:
        colour = BAND_COLOURS.get(a["band"], "#4b5563")
        return (f'<li style="margin:6px 0">{e(a["text"])} '
                f'<span style="color:{colour};font-weight:600">({e(a["bandName"])})</span> '
                f'<code style="color:#4b5563">[{e(", ".join(a["ruleIds"]))}]</code></li>')

    changes = [a for a in brief["actions"] if a["change"] and a["kind"] != "note"]
    same = [a for a in brief["actions"] if not a["change"] and a["kind"] != "note"]
    pn = brief["parentNote"]
    parts = ['<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;color:#111827;line-height:1.5">']
    if brief["mode"] == "replay":
        parts.append(f'<p style="background:#fef3c7;padding:8px;border-radius:4px"><strong>REPLAY</strong> of '
                     f'{e(brief["date"])} using archived data.</p>')
    parts.append(f'<h1 style="font-size:20px;margin:0 0 8px">{e(brief["subject"])}</h1>')
    parts.append(f'<p style="margin:4px 0">{e(_official_line(o))}<br>{e(g["label"])}</p>')
    parts.append(f'<p style="margin:4px 0"><strong>{e(brief["headline"])}</strong></p>')
    parts.append(f'<h2 style="font-size:16px;margin:16px 0 4px">{"What changes today" if changes else "No changes today"}</h2>')
    if changes:
        parts.append("<ul>" + "".join(row(a) for a in changes) + "</ul>")
    if same:
        parts.append('<h2 style="font-size:16px;margin:16px 0 4px">As normal</h2>')
        parts.append("<ul>" + "".join(row(a) for a in same) + "</ul>")
    if pn["send"]:
        label = "optional" if pn["optional"] else "recommended"
        parts.append(f'<h2 style="font-size:16px;margin:16px 0 4px">Parent note ({label})</h2>')
        parts.append(f'<p>{e(pn["en"])}</p><p lang="hi">{e(pn["hi"])}</p>')
    else:
        parts.append("<p>No parent note needed today.</p>")
    if dashboard_url:
        parts.append(f'<p><a href="{e(dashboard_url)}">Open the dashboard</a> to copy the note for WhatsApp.</p>')
    parts.append(f'<p style="font-size:12px;color:#4b5563">As of {e(brief["generatedAt"][11:16])} IST. '
                 f'{e(ATTRIBUTION)}</p></div>')
    return "".join(parts)


def ses_sender(source: str) -> Callable[[str, str, str, str], str]:
    import boto3

    client = boto3.client("sesv2")

    def send(to: str, subject: str, text: str, html_body: str) -> str:
        r = client.send_email(
            FromEmailAddress=source,
            Destination={"ToAddresses": [to]},
            Content={"Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": text, "Charset": "UTF-8"},
                         "Html": {"Data": html_body, "Charset": "UTF-8"}},
            }},
        )
        return r["MessageId"]

    return send


def send_daily(store: Store, brief: dict, to: str, send: Callable[[str, str, str, str], str],
               dashboard_url: str = "", now: Callable[[], float] = time.time) -> dict[str, Any]:
    """Claim, send, record. At most one automatic email per date; a known failure is retried by the
    next invocation (Scheduler retry) up to MAX_ATTEMPTS. Raises on send failure so the caller fails."""
    key = f"EMAIL#{brief['date']}"
    try:
        claim = store.claim_email(school_pk(), key, now(), MAX_ATTEMPTS)
    except ConditionFailed as e:
        log.info("email for %s not sent: already %s", brief["date"], e)
        return {"sent": False, "reason": f"already {e}"}
    try:
        mid = send(to, brief["subject"], render_text(brief, dashboard_url), render_html(brief, dashboard_url))
    except Exception as e:
        store.set_email_status(school_pk(), key, "FAILED", now(), error=str(e)[:300])
        log.error("email send failed (attempt %s): %s", claim["attempts"], e)
        raise
    store.set_email_status(school_pk(), key, "SENT", now(), messageId=mid)
    return {"sent": True, "messageId": mid, "attempts": claim["attempts"]}


def send_once_more(brief: dict, to: str, send: Callable[[str, str, str, str], str], dashboard_url: str = "") -> str:
    """Manual resend or replay email. Never touches the daily lock."""
    return send(to, brief["subject"], render_text(brief, dashboard_url), render_html(brief, dashboard_url))


def configured_sender() -> Callable[[str, str, str, str], str] | None:
    src = os.environ.get("SES_SENDER")
    return ses_sender(src) if src else None
