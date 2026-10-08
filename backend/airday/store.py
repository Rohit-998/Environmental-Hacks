"""Storage. One interface, two backends: in-memory (dev server, tests) and DynamoDB single table.

Keys (PRD §12), one partition per tenant plus two shared partitions:
  SCHOOL#<id> / PROFILE, ACTIVITY#<id>, BRIEF#<date>, REPLAY#<date>, EMAIL#<date>
  REGISTRY    / SCHOOL#<id>                    school index for the planner
  CACHE       / openmeteo#<grid>#<date>, ...   upstream responses shared by every school in a grid cell
  COUNTER#<date> / AGENT#<id>                  per-tenant daily agent cap
"""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from decimal import Decimal
from typing import Any, Protocol

DEMO_SCHOOL = "demo"
CACHE_PK = "CACHE"        # shared upstream cache, keyed by forecast grid cell / sensor, not by school
REGISTRY_PK = "REGISTRY"  # one row per school, read by the 06:00 planner


class ConditionFailed(Exception):
    """A conditional write did not apply."""


class Store(Protocol):
    def get(self, pk: str, sk: str) -> dict | None: ...
    def put(self, pk: str, sk: str, item: dict) -> None: ...
    def delete(self, pk: str, sk: str) -> None: ...
    def query_prefix(self, pk: str, sk_prefix: str) -> list[dict]: ...
    def claim_email(self, pk: str, sk: str, now: float, max_attempts: int) -> dict: ...
    def set_email_status(self, pk: str, sk: str, status: str, now: float, **extra: Any) -> None: ...
    def incr(self, pk: str, sk: str, ttl: int | None = None) -> int: ...


def school_pk(school_id: str) -> str:
    return f"SCHOOL#{school_id}"


# ---------------------------------------------------------------- memory

class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict] = {}
        self._lock = threading.Lock()

    def get(self, pk, sk):
        with self._lock:
            v = self._items.get((pk, sk))
            return copy.deepcopy(v) if v is not None else None

    def put(self, pk, sk, item):
        with self._lock:
            self._items[(pk, sk)] = copy.deepcopy(item)

    def delete(self, pk, sk):
        with self._lock:
            self._items.pop((pk, sk), None)

    def query_prefix(self, pk, sk_prefix):
        with self._lock:
            return [copy.deepcopy(v) | {"SK": k[1]} for k, v in sorted(self._items.items())
                    if k[0] == pk and k[1].startswith(sk_prefix)]

    def claim_email(self, pk, sk, now, max_attempts):
        with self._lock:
            cur = self._items.get((pk, sk))
            if cur is not None and not (cur["status"] == "FAILED" and cur["attempts"] < max_attempts):
                raise ConditionFailed(cur["status"])
            attempts = (cur["attempts"] if cur else 0) + 1
            item = {"status": "SENDING", "attempts": attempts, "updatedAt": now}
            self._items[(pk, sk)] = item
            return dict(item)

    def set_email_status(self, pk, sk, status, now, **extra):
        with self._lock:
            item = self._items.setdefault((pk, sk), {"attempts": 0})
            item.update({"status": status, "updatedAt": now, **extra})

    def incr(self, pk, sk, ttl=None):
        with self._lock:
            item = self._items.setdefault((pk, sk), {"n": 0})
            item["n"] += 1
            return item["n"]


# ---------------------------------------------------------------- DynamoDB

def _to_ddb(v: Any) -> Any:
    """Floats are not allowed in DynamoDB; round-trip through JSON with Decimal."""
    return json.loads(json.dumps(v), parse_float=Decimal)


def _from_ddb(v: Any) -> Any:
    if isinstance(v, list):
        return [_from_ddb(x) for x in v]
    if isinstance(v, dict):
        return {k: _from_ddb(x) for k, x in v.items()}
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


class DynamoStore:
    def __init__(self, table_name: str | None = None, client: Any = None) -> None:
        import boto3  # available in the Lambda runtime

        self.table = (client or boto3.resource("dynamodb")).Table(table_name or os.environ["TABLE_NAME"])

    def get(self, pk, sk):
        r = self.table.get_item(Key={"PK": pk, "SK": sk}).get("Item")
        if r is None:
            return None
        r = _from_ddb(r)
        r.pop("PK", None)
        r.pop("SK", None)
        # Regular items are wrapped in "data"; email-state items keep top-level attributes.
        return r["data"] if "data" in r else r

    def put(self, pk, sk, item):
        self.table.put_item(Item={"PK": pk, "SK": sk, "data": _to_ddb(item)})

    def delete(self, pk, sk):
        self.table.delete_item(Key={"PK": pk, "SK": sk})

    def query_prefix(self, pk, sk_prefix):
        from boto3.dynamodb.conditions import Key

        out, kwargs = [], {"KeyConditionExpression": Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix)}
        while True:
            resp = self.table.query(**kwargs)
            for r in resp.get("Items", []):
                r = _from_ddb(r)
                data = r.get("data", {})
                out.append(data | {"SK": r["SK"]})
            if "LastEvaluatedKey" not in resp:
                return out
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def claim_email(self, pk, sk, now, max_attempts):
        from botocore.exceptions import ClientError

        try:
            resp = self.table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression="SET #s = :sending, updatedAt = :now ADD attempts :one",
                ConditionExpression="attribute_not_exists(PK) OR (#s = :failed AND attempts < :max)",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":sending": "SENDING", ":failed": "FAILED", ":one": 1,
                                           ":max": max_attempts, ":now": Decimal(str(now))},
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConditionFailed("email already claimed") from e
            raise
        a = _from_ddb(resp["Attributes"])
        return {"status": a["status"], "attempts": a["attempts"], "updatedAt": a["updatedAt"]}

    def set_email_status(self, pk, sk, status, now, **extra):
        names = {"#s": "status"}
        values = {":s": status, ":now": Decimal(str(now))}
        sets = ["#s = :s", "updatedAt = :now"]
        for i, (k, v) in enumerate(extra.items()):
            names[f"#e{i}"] = k
            values[f":e{i}"] = _to_ddb(v)
            sets.append(f"#e{i} = :e{i}")
        self.table.update_item(Key={"PK": pk, "SK": sk}, UpdateExpression="SET " + ", ".join(sets),
                               ExpressionAttributeNames=names, ExpressionAttributeValues=values)

    def incr(self, pk, sk, ttl=None):
        expr, values = "ADD n :one", {":one": 1}
        if ttl:
            expr += " SET expiresAt = if_not_exists(expiresAt, :ttl)"
            values[":ttl"] = int(time.time()) + ttl
        resp = self.table.update_item(Key={"PK": pk, "SK": sk}, UpdateExpression=expr,
                                      ExpressionAttributeValues=values, ReturnValues="UPDATED_NEW")
        return int(resp["Attributes"]["n"])


_default: Store | None = None


def default_store() -> Store:
    global _default
    if _default is None:
        _default = DynamoStore() if os.environ.get("TABLE_NAME") else MemoryStore()
    return _default
