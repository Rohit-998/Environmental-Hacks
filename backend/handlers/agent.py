"""Lambda handler for /chat and /note/translate (separate Lambda: bigger package, longer timeout)."""
from __future__ import annotations

import base64
import json
import logging

from airday import agent, api
from airday.store import default_store
from handlers.api import _load_admin_key

logging.getLogger().setLevel(logging.INFO)
_load_admin_key()


def handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    body = event.get("body")
    if body and event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    status, out = api.route(http.get("method", "POST"), event.get("rawPath", "/"),
                            event.get("queryStringParameters") or {}, body,
                            event.get("headers") or {}, default_store(), extra=agent.ROUTES)
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(out, ensure_ascii=False),
    }
