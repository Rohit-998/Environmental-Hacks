"""Lambda handler for the HTTP API (API Gateway HTTP API, payload format 2.0)."""
from __future__ import annotations

import base64
import json
import logging
import os

from airday import api
from airday.store import default_store

logging.getLogger().setLevel(logging.INFO)
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()}


def _load_admin_key() -> None:
    """ADMIN_KEY comes from SSM SecureString; read once per cold start."""
    name = os.environ.get("ADMIN_KEY_PARAM")
    if name and not os.environ.get("ADMIN_KEY"):
        import boto3

        os.environ["ADMIN_KEY"] = boto3.client("ssm").get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]


_load_admin_key()


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
