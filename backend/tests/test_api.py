import json

import pytest

from airday import api
from airday.store import MemoryStore


@pytest.fixture(autouse=True)
def admin(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "secret")


def call(store, method, path, query=None, body=None, headers=None):
    if isinstance(body, (dict, list)):
        body = json.dumps(body)
        headers = {"content-type": "application/json", **(headers or {})}
    return api.route(method, path, query or {}, body, headers or {}, store)


ADMIN = {"x-admin-key": "secret"}


def test_public_school_hides_email_and_admin_can_update():
    s = MemoryStore()
    status, body = call(s, "PUT", "/school", body={"principalEmail": "p@example.com"}, headers=ADMIN)
    assert status == 200 and "principalEmail" not in body and body["hasEmail"]
    status, body = call(s, "GET", "/school")
    assert status == 200 and "principalEmail" not in body


def test_writes_need_the_admin_key():
    s = MemoryStore()
    assert call(s, "PUT", "/school", body={"name": "X"})[0] == 401
    assert call(s, "PUT", "/school", body={"name": "X"}, headers={"x-admin-key": "wrong"})[0] == 401
    assert call(s, "PUT", "/school", body={"bogus": 1}, headers=ADMIN)[0] == 400


def test_grap_override_gets_an_expiry():
    s = MemoryStore()
    _, body = call(s, "PUT", "/school", body={"grapOverride": {"stage": "III"}}, headers=ADMIN)
    assert body["grapOverride"]["expiresAt"]


def test_timetable_csv_upload_returns_row_errors():
    s = MemoryStore()
    status, body = call(s, "PUT", "/activities", body="Mon,08:40,09:20,pe,6B\nXyz,08:00,08:30,pe,X",
                        headers=ADMIN | {"content-type": "text/csv"})
    assert status == 400 and body["rowErrors"][0]["line"] == 2
    status, body = call(s, "PUT", "/activities", body="Mon,08:40,09:20,pe,6B",
                        headers=ADMIN | {"content-type": "text/csv"})
    assert status == 200 and len(body["activities"]) == 1
    assert len(call(s, "GET", "/activities")[1]["activities"]) == 1


def test_replay_endpoints():
    s = MemoryStore()
    status, body = call(s, "GET", "/replay/dates")
    assert status == 200 and "2025-11-19" in body["dates"]
    status, body = call(s, "GET", "/replay", {"date": "2025-11-19"})
    assert status == 200 and body["mode"] == "replay"
    assert call(s, "GET", "/replay", {"date": "2020-01-01"})[0] == 404
    assert call(s, "GET", "/replay", {"date": "nope"})[0] == 400


def test_cors_preflight_is_a_204_on_any_path():
    s = MemoryStore()
    assert call(s, "OPTIONS", "/replay/dates") == (204, None)
    assert call(s, "OPTIONS", "/me/school")[0] == 204
    assert call(s, "OPTIONS", "/does-not-exist")[0] == 204


def test_evaluate_and_rules_and_errors():
    s = MemoryStore()
    status, body = call(s, "GET", "/evaluate",
                        {"type": "pe", "date": "2025-11-20", "start": "14:00", "end": "16:00", "mode": "replay"})
    assert status == 200 and body["ruleId"].endswith("-PE")
    assert call(s, "GET", "/evaluate", {"type": "swim", "date": "2025-11-20", "start": "14:00",
                                         "end": "16:00", "mode": "replay"})[0] == 400
    assert call(s, "GET", "/rules")[1]["version"]
    assert call(s, "GET", "/nope")[0] == 404
    assert call(s, "DELETE", "/school")[0] == 405


def test_windows_endpoint_returns_three_days():
    s = MemoryStore()
    status, body = call(s, "GET", "/windows",
                        {"type": "pe", "date": "2025-11-19", "mode": "replay", "duration": "2"})
    assert status == 200 and body["type"] == "pe" and len(body["days"]) == 3
    assert body["days"][0]["windows"] == []  # Severe replay morning: no clear PE window
    assert call(s, "GET", "/windows", {"type": "lunch", "date": "2025-11-19", "mode": "replay"})[0] == 400
