"""Who is calling, and which school (tenant) they may act on.

Two entry points, both resolved to a Principal before any handler runs:

  /me/...   Cognito user. API Gateway's JWT authorizer has already verified the token; we read the `sub`
            claim and look up the school that user owns. The school ID never comes from the client.
  /...      Public demo. Read-only access to the demo school. Writes need the demo admin key, and only
            when DEMO_ADMIN is enabled (local dev and the hackathon demo; off in a real deployment).
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from .store import DEMO_SCHOOL, Store


@dataclass(frozen=True)
class Principal:
    kind: str                 # "user" | "demo-admin" | "anonymous"
    sub: str | None           # Cognito user ID for kind == "user"
    school_id: str | None     # None for a signed-in user who hasn't created a school yet
    can_write: bool

    def public(self) -> dict:
        return {"kind": self.kind, "schoolId": self.school_id, "canWrite": self.can_write,
                "demo": self.school_id == DEMO_SCHOOL}


def demo_admin_enabled() -> bool:
    return os.environ.get("DEMO_ADMIN", "true").lower() == "true" and bool(os.environ.get("ADMIN_KEY"))


def demo_principal(headers: dict[str, str]) -> Principal:
    expected = os.environ.get("ADMIN_KEY", "")
    got = headers.get("x-admin-key", "")
    ok = demo_admin_enabled() and bool(got) and hmac.compare_digest(got.encode(), expected.encode())
    return Principal("demo-admin" if ok else "anonymous", None, DEMO_SCHOOL, ok)


def user_principal(store: Store, claims: dict) -> Principal:
    from .service import school_for_user

    sub = claims.get("sub")
    if not sub:
        raise PermissionError("token has no sub claim")
    return Principal("user", sub, school_for_user(store, sub), True)
