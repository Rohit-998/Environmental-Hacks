"""Lambda entry points: event shapes in, response shapes out. Uses the in-memory store (no TABLE_NAME)."""
import json
from types import SimpleNamespace

import pytest

CTX = SimpleNamespace(function_name="f", memory_limit_in_mb=512, aws_request_id="r1",
                      invoked_function_arn="arn:aws:lambda:ap-south-1:1:function:f")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.delenv("TABLE_NAME", raising=False)
    monkeypatch.setenv("ADMIN_KEY", "x")


def http(path, method="GET", query=None, claims=None, body=None):
    ctx = {"http": {"method": method}}
    if claims:
        ctx["authorizer"] = {"jwt": {"claims": claims}}
    return {"rawPath": path, "queryStringParameters": query, "requestContext": ctx, "body": body}


def test_api_handler_serves_demo_and_reads_jwt_claims():
    from handlers import api

    r = api.handler(http("/replay", query={"date": "2025-11-19"}), CTX)
    assert r["statusCode"] == 200 and json.loads(r["body"])["mode"] == "replay"
    r = api.handler(http("/me", claims={"sub": "u-handler"}), CTX)
    assert r["statusCode"] == 200 and json.loads(r["body"])["kind"] == "user"
    assert api.handler(http("/me"), CTX)["statusCode"] == 401


def test_api_handler_answers_cors_preflight_with_empty_204():
    from handlers import api

    r = api.handler(http("/replay/dates", method="OPTIONS"), CTX)
    assert r == {"statusCode": 204, "body": ""}


def test_worker_handler_returns_partial_batch_response():
    from handlers import worker

    records = [
        {"messageId": "sunday", "body": json.dumps({"schoolId": "demo", "date": "2025-11-23"})},
        {"messageId": "bad", "body": "not json"},
    ]
    assert worker.handler({"Records": records}, CTX) == {"batchItemFailures": [{"itemIdentifier": "bad"}]}


def test_planner_handler_enqueues_one_job_per_school(monkeypatch):
    from airday import service
    from handlers import planner

    monkeypatch.setattr(service, "warm_forecast", lambda *a: "fresh")
    sent = []
    monkeypatch.setattr(planner, "_enqueue", sent.extend)
    out = planner.handler({"date": "2025-11-19"}, CTX)
    assert out["schools"] >= 1 and len(sent) == out["schools"]
