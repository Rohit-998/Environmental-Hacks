"""The real DynamoStore against moto's DynamoDB, so the first deploy isn't the first time it runs."""
import datetime as dt
import json

import boto3
import pytest
from moto import mock_aws

from airday import fanout, mailer, service
from airday.store import ConditionFailed, DynamoStore
from airday.timeutil import IST


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")
        ddb.create_table(
            TableName="airday-test",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"},
                                  {"AttributeName": "SK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoStore("airday-test", client=ddb)


def test_put_get_roundtrip_keeps_floats_ints_nested_and_unicode(store):
    item = {"pm25": 187.4, "n": 3, "hours": [7, 8], "nested": {"a": None, "b": [1.5]}, "hi": "बहुत खराब"}
    store.put("SCHOOL#x", "PROFILE", item)
    assert store.get("SCHOOL#x", "PROFILE") == item
    assert store.get("SCHOOL#x", "MISSING") is None


def test_query_prefix_returns_items_with_sk_and_pages(store):
    for i in range(30):
        store.put("SCHOOL#x", f"ACTIVITY#{i:02d}", {"i": i, "pad": "x" * 2000})
    store.put("SCHOOL#x", "PROFILE", {"name": "n"})
    rows = store.query_prefix("SCHOOL#x", "ACTIVITY#")
    assert [r["i"] for r in rows] == list(range(30))
    assert rows[0]["SK"] == "ACTIVITY#00"
    store.delete("SCHOOL#x", "ACTIVITY#00")
    assert len(store.query_prefix("SCHOOL#x", "ACTIVITY#")) == 29


def test_email_claim_protocol_on_dynamodb(store):
    store.claim_email("S", "EMAIL#d", 1.0, 3)
    with pytest.raises(ConditionFailed):
        store.claim_email("S", "EMAIL#d", 2.0, 3)
    store.set_email_status("S", "EMAIL#d", "FAILED", 3.0, error="throttled")
    assert store.claim_email("S", "EMAIL#d", 4.0, 3)["attempts"] == 2
    store.set_email_status("S", "EMAIL#d", "SENT", 5.0, messageId="m-1")
    with pytest.raises(ConditionFailed):
        store.claim_email("S", "EMAIL#d", 6.0, 3)
    state = store.get("S", "EMAIL#d")
    assert state["status"] == "SENT" and state["messageId"] == "m-1" and state["attempts"] == 2


def test_claims_stop_after_max_attempts(store):
    for _ in range(3):
        store.claim_email("S", "EMAIL#d", 1.0, 3)
        store.set_email_status("S", "EMAIL#d", "FAILED", 1.0)
    with pytest.raises(ConditionFailed):
        store.claim_email("S", "EMAIL#d", 1.0, 3)


def test_counter_increments_atomically_with_ttl(store):
    assert [store.incr("COUNTER#d", "AGENT#s", ttl=60) for _ in range(3)] == [1, 2, 3]


def test_full_daily_run_on_dynamodb(store, monkeypatch):
    """Planner, worker, brief storage and email claim end to end on the real store."""
    def fake(lat, lon, start, end):
        days = [dt.date.fromisoformat(start) + dt.timedelta(days=i) for i in range(3)]
        times = [f"{d}T{h:02d}:00" for d in days for h in range(24)]
        return {"hourly": {"time": times, "pm2_5": [180.5] * len(times), "pm10": [300.0] * len(times)}}

    monkeypatch.setattr(service.sources, "fetch_open_meteo", fake)
    sid = service.create_school(store, {"name": "Rohini", "lat": 28.74, "lon": 77.08,
                                        "principalEmail": "p@example.com"}, owner="u1")
    assert service.school_for_user(store, "u1") == sid
    service.replace_timetable(store, sid, [{"id": "a1", "day": "Wed", "start": "08:40", "end": "09:20",
                                            "type": "pe", "label": "Class 6B PE"}])

    queued = []
    summary = fanout.plan(store, dt.date(2025, 11, 19), queued.extend)
    assert summary["schools"] == 1 and summary["gridCells"] == 1

    sent = []

    def ses(to, subject, text, html):
        sent.append(subject)
        return "m-1"

    six = dt.datetime(2025, 11, 19, 6, 0, tzinfo=IST)
    records = [{"messageId": "m", "body": json.dumps(queued[0])}]
    assert fanout.process_batch(store, records, six, ses)["batchItemFailures"] == []
    assert fanout.process_batch(store, records, six, ses)["batchItemFailures"] == []  # SQS redelivery
    assert len(sent) == 1

    brief = service.get_stored(store, sid, "2025-11-19")
    assert brief["schoolId"] == sid and any(a["ruleIds"] == ["R-VP-PE"] for a in brief["actions"])
    assert isinstance(brief["hours"][8]["pm25"], float)
    assert mailer.MAX_ATTEMPTS == 3
