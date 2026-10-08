import datetime as dt
import json

import pytest

from airday import api, fanout, service
from airday.store import MemoryStore
from airday.timeutil import IST

SIX_AM = dt.datetime(2025, 11, 19, 6, 0, tzinfo=IST)
WED = dt.date(2025, 11, 19)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "secret")


@pytest.fixture
def forecast_calls(monkeypatch):
    """Fake Open-Meteo: Very Poor all morning. Records every (lat, lon) fetched."""
    calls = []

    def fake(lat, lon, start, end):
        calls.append((lat, lon))
        days = [dt.date.fromisoformat(start) + dt.timedelta(days=i) for i in range(3)]
        times = [f"{d}T{h:02d}:00" for d in days for h in range(24)]
        return {"hourly": {"time": times, "pm2_5": [180.0] * len(times), "pm10": [300.0] * len(times)}}

    monkeypatch.setattr(service.sources, "fetch_open_meteo", fake)
    return calls


def call(store, method, path, sub=None, body=None, headers=None, query=None):
    if isinstance(body, dict):
        body = json.dumps(body)
        headers = {"content-type": "application/json", **(headers or {})}
    return api.route(method, path, query or {}, body, headers or {}, store, claims={"sub": sub} if sub else None)


def make_school(store, sub, name, lat=28.74, lon=77.08, email=None):
    body = {"name": name, "lat": lat, "lon": lon}
    if email:
        body["principalEmail"] = email
    status, out = call(store, "POST", "/me/school", sub=sub, body=body)
    assert status == 201, out
    call(store, "PUT", "/me/activities", sub=sub, body="Wed,08:40,09:20,pe,Class 6B PE",
         headers={"content-type": "text/csv"})
    return out["schoolId"]


# ---------------------------------------------------------------- tenancy

def test_me_requires_a_signed_in_user():
    s = MemoryStore()
    assert call(s, "GET", "/me")[0] == 401
    assert call(s, "GET", "/me", sub="u1")[1] == {"kind": "user", "schoolId": None, "canWrite": True, "demo": False}
    assert call(s, "GET", "/me/school", sub="u1")[0] == 404


def test_users_only_see_their_own_school():
    s = MemoryStore()
    a = make_school(s, "alice", "Alice School")
    b = make_school(s, "bob", "Bob School")
    assert a != b
    assert call(s, "GET", "/me/school", sub="alice")[1]["name"] == "Alice School"
    assert call(s, "GET", "/me/school", sub="bob")[1]["name"] == "Bob School"
    assert len(call(s, "GET", "/me/activities", sub="alice")[1]["activities"]) == 1
    # The school ID is never taken from the client: a query parameter is ignored.
    assert call(s, "GET", "/me/school", sub="bob", query={"schoolId": a})[1]["name"] == "Bob School"


def test_one_school_per_user_and_demo_stays_public():
    s = MemoryStore()
    make_school(s, "alice", "Alice School")
    assert call(s, "POST", "/me/school", sub="alice", body={"name": "Again", "lat": 28.7, "lon": 77.1})[0] == 409
    assert call(s, "GET", "/school")[1]["name"] == "Sunrise Public School"
    assert call(s, "PUT", "/school", body={"name": "Hacked"})[0] == 401


def test_demo_writes_can_be_disabled(monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN", "false")
    s = MemoryStore()
    assert call(s, "PUT", "/school", body={"name": "X"}, headers={"x-admin-key": "secret"})[0] == 401


# ---------------------------------------------------------------- fan-out

def test_planner_fetches_one_forecast_per_grid_cell(forecast_calls):
    s = MemoryStore()
    make_school(s, "a", "Rohini", 28.74, 77.08)
    make_school(s, "b", "Pitampura", 28.70, 77.13)   # same 0.4° cell as Rohini
    make_school(s, "c", "Noida", 28.54, 77.39)       # different cell
    queued = []
    summary = fanout.plan(s, WED, queued.extend)
    assert summary["schools"] == 3 and summary["gridCells"] == 2
    assert len(forecast_calls) == 2 and len(queued) == 3

    for job in queued:
        fanout.run_job(s, job, SIX_AM, None)
    assert len(forecast_calls) == 2  # workers hit the shared cache


def test_worker_builds_and_emails_once_even_if_sqs_redelivers(forecast_calls):
    s = MemoryStore()
    sid = make_school(s, "a", "Rohini", email="p@example.com")
    sent = []

    def ses(to, subject, text, html):
        sent.append((to, subject))
        return "m-1"

    job = {"schoolId": sid, "date": WED.isoformat()}
    r1 = fanout.run_job(s, job, SIX_AM, ses)
    r2 = fanout.run_job(s, job, SIX_AM, ses)
    assert r1["email"]["sent"] and not r2["email"]["sent"]
    assert len(sent) == 1 and "6B" not in sent[0][1] and "change" in sent[0][1]
    assert r1["ruleIds"] and "R-VP-PE" in r1["ruleIds"]
    assert service.get_stored(s, sid, WED.isoformat())["schoolId"] == sid


def test_batch_reports_partial_failures(forecast_calls):
    s = MemoryStore()
    sid = make_school(s, "a", "Rohini")
    records = [
        {"messageId": "ok", "body": json.dumps({"schoolId": sid, "date": WED.isoformat()})},
        {"messageId": "bad", "body": json.dumps({"schoolId": "missing", "date": WED.isoformat()})},
    ]
    out = fanout.process_batch(s, records, SIX_AM, None)
    assert out["batchItemFailures"] == [{"itemIdentifier": "bad"}]


def test_worker_skips_non_school_days_and_late_runs(forecast_calls):
    s = MemoryStore()
    sid = make_school(s, "a", "Rohini")
    sunday = {"schoolId": sid, "date": "2025-11-23"}
    assert fanout.run_job(s, sunday, SIX_AM, None)["skipped"]
    late = dt.datetime(2025, 11, 19, 8, 0, tzinfo=IST)
    assert fanout.run_job(s, {"schoolId": sid, "date": WED.isoformat()}, late, None)["reason"].startswith("after")


def test_grid_key_snaps_to_cams_cells():
    assert service.grid_key(28.74, 77.08)[0] == service.grid_key(28.70, 77.13)[0]
    assert service.grid_key(28.74, 77.08)[0] != service.grid_key(28.54, 77.39)[0]
