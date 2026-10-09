"""SES sandbox recipient verification: request on save, track status, skip unverified at 06:00."""
import datetime as dt
import json

import pytest

from airday import api, fanout, service, verify
from airday.store import MemoryStore
from airday.timeutil import IST

SIX_AM = dt.datetime(2025, 11, 19, 6, 0, tzinfo=IST)


class FakeVerifier:
    def __init__(self):
        self.known: dict[str, str] = {}
        self.requests: list[str] = []

    def request(self, email):
        self.requests.append(email)
        self.known.setdefault(email, verify.PENDING)
        return self.known[email]

    def status(self, email):
        return self.known.get(email, verify.FAILED)

    def deliverable(self, email):
        return self.status(email) == verify.VERIFIED


@pytest.fixture
def fv(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "secret")
    v = FakeVerifier()
    verify.set_verifier(v)
    yield v
    verify.set_verifier(None)


def call(store, method, path, sub=None, body=None):
    headers = {"content-type": "application/json"}
    return api.route(method, path, {}, json.dumps(body) if body is not None else None, headers, store,
                     claims={"sub": sub} if sub else None)


def test_new_email_requests_verification_and_reports_pending(fv):
    s = MemoryStore()
    status, out = call(s, "POST", "/me/school", sub="u1", body={"name": "R", "lat": 28.7, "lon": 77.1,
                                                                  "principalEmail": "p@school.in"})
    assert status == 201 and out["emailStatus"] == verify.PENDING
    assert fv.requests == ["p@school.in"]
    assert "principalEmail" not in out


def test_status_flips_to_verified_after_the_link_is_clicked(fv):
    s = MemoryStore()
    call(s, "POST", "/me/school", sub="u1", body={"name": "R", "lat": 28.7, "lon": 77.1, "principalEmail": "p@school.in"})
    fv.known["p@school.in"] = verify.VERIFIED  # principal clicked the AWS link
    assert call(s, "GET", "/me/school", sub="u1")[1]["emailStatus"] == verify.VERIFIED


def test_unchanged_email_is_not_re_requested_but_a_new_one_is(fv):
    s = MemoryStore()
    call(s, "POST", "/me/school", sub="u1", body={"name": "R", "lat": 28.7, "lon": 77.1, "principalEmail": "a@x.in"})
    call(s, "PUT", "/me/school", sub="u1", body={"name": "Renamed"})
    assert fv.requests == ["a@x.in"]
    call(s, "PUT", "/me/school", sub="u1", body={"principalEmail": "b@x.in"})
    assert fv.requests == ["a@x.in", "b@x.in"]


def test_resend_endpoint(fv):
    s = MemoryStore()
    call(s, "POST", "/me/school", sub="u1", body={"name": "R", "lat": 28.7, "lon": 77.1, "principalEmail": "a@x.in"})
    status, out = call(s, "POST", "/me/school/verify-email", sub="u1")
    assert status == 200 and fv.requests == ["a@x.in", "a@x.in"]


def test_worker_skips_sending_to_unverified_address_without_failing(fv, monkeypatch):
    def fake(lat, lon, start, end):
        days = [dt.date.fromisoformat(start) + dt.timedelta(days=i) for i in range(3)]
        times = [f"{d}T{h:02d}:00" for d in days for h in range(24)]
        return {"hourly": {"time": times, "pm2_5": [180.0] * len(times), "pm10": [300.0] * len(times)}}

    monkeypatch.setattr(service.sources, "fetch_open_meteo", fake)
    s = MemoryStore()
    call(s, "POST", "/me/school", sub="u1", body={"name": "R", "lat": 28.7, "lon": 77.1, "principalEmail": "p@school.in"})
    sid = service.school_for_user(s, "u1")
    sent = []
    r = fanout.run_job(s, {"schoolId": sid, "date": "2025-11-19"}, SIX_AM, lambda *a: sent.append(a) or "m")
    assert r["valid"] and not r["email"]["sent"] and "not verified" in r["email"]["reason"]
    assert sent == [] and service.get_stored(s, sid, "2025-11-19") is not None

    fv.known["p@school.in"] = verify.VERIFIED
    r = fanout.run_job(s, {"schoolId": sid, "date": "2025-11-19"}, SIX_AM, lambda *a: sent.append(a) or "m")
    assert r["email"]["sent"] and len(sent) == 1


def test_no_ses_means_every_address_is_deliverable():
    v = verify.NoVerifier()
    assert v.deliverable("anyone@example.com") and v.request("x@y.z") == verify.NOT_CHECKED
