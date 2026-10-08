"""Lambda handler for the HTTP API (API Gateway HTTP API, payload format 2.0)."""
from __future__ import annotations

import base64
import json
import logging
import os

from airday import api, secrets
from airday.store import default_store

logging.getLogger().setLevel(logging.INFO)
secrets.load()


def handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    body = event.get("body")
    if body and event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    status, out = api.route(http.get("method", "GET"), event.get("rawPath", "/"),
                            event.get("queryStringParameters") or {}, body,
                            event.get("headers") or {}, default_store())
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(out, ensure_ascii=False),
    }
