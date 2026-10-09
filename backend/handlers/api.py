"""Lambda handler for the HTTP API (API Gateway HTTP API, payload format 2.0).

/me/* routes sit behind the Cognito JWT authorizer; API Gateway verifies the token and passes the claims in
requestContext.authorizer.jwt.claims. Public demo routes have no authorizer.
"""
from __future__ import annotations

import base64
import json

from airday import api, obs, secrets
from airday.store import default_store

secrets.load()


def claims_of(event: dict) -> dict | None:
    return ((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt", {}).get("claims")


def respond(event: dict, extra: dict | None = None) -> dict:
    http = event.get("requestContext", {}).get("http", {})
    body = event.get("body")
    if body and event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    path = event.get("rawPath", "/")
    obs.annotate(route=f"{http.get('method', 'GET')} {path}")
    status, out = api.route(http.get("method", "GET"), path, event.get("queryStringParameters") or {}, body,
                            event.get("headers") or {}, default_store(), extra=extra, claims=claims_of(event))
    obs.count(f"Http{status // 100}xx")
    if out is None:  # e.g. a 204 CORS preflight: no body
        return {"statusCode": status, "body": ""}
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(out, ensure_ascii=False),
    }


@obs.logger.inject_lambda_context(log_event=False) if obs.ENABLED else (lambda f: f)
@obs.tracer.capture_lambda_handler
@obs.metrics.log_metrics
def handler(event, context):
    return respond(event)
