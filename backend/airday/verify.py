"""Recipient email verification for the SES sandbox.

While the AWS account is in the SES sandbox, SES only delivers to verified addresses. So when a principal saves
an email, AirDay asks SES to send them a verification link, and the 06:00 run skips schools whose address isn't
verified yet (instead of failing three times and alarming). With SES production access every address is
deliverable and verification is a no-op.

Locally (no SES_SENDER) there is no SES: every address counts as deliverable and status is "not-checked".
"""
from __future__ import annotations

import logging
import os
from typing import Protocol

log = logging.getLogger("airday")

VERIFIED, PENDING, FAILED, NOT_CHECKED = "verified", "pending", "failed", "not-checked"


class Verifier(Protocol):
    def request(self, email: str) -> str: ...
    def status(self, email: str) -> str: ...
    def deliverable(self, email: str) -> bool: ...


class SesVerifier:
    def __init__(self, client=None) -> None:
        import boto3

        self.ses = client or boto3.client("sesv2")
        self._production: bool | None = None

    def production(self) -> bool:
        if self._production is None:
            try:
                self._production = bool(self.ses.get_account().get("ProductionAccessEnabled"))
            except Exception as e:  # don't block on a read failure; assume sandbox
                log.warning("SES get_account failed: %s", e)
                return False
        return self._production

    def status(self, email: str) -> str:
        if self.production():
            return VERIFIED
        try:
            r = self.ses.get_email_identity(EmailIdentity=email)
        except self.ses.exceptions.NotFoundException:
            return FAILED
        if r.get("VerifiedForSendingStatus"):
            return VERIFIED
        return {"PENDING": PENDING, "SUCCESS": VERIFIED}.get(r.get("VerificationStatus", ""), FAILED)

    def request(self, email: str) -> str:
        """Ask SES to email a verification link. Safe to call again for an address SES already knows."""
        if self.production():
            return VERIFIED
        try:
            self.ses.create_email_identity(EmailIdentity=email)
            return PENDING
        except self.ses.exceptions.AlreadyExistsException:
            return self.status(email)

    def deliverable(self, email: str) -> bool:
        return self.status(email) == VERIFIED


class NoVerifier:
    """Local dev and tests without SES."""

    def request(self, email: str) -> str:
        return NOT_CHECKED

    def status(self, email: str) -> str:
        return NOT_CHECKED

    def deliverable(self, email: str) -> bool:
        return True


_verifier: Verifier | None = None


def verifier() -> Verifier:
    global _verifier
    if _verifier is None:
        _verifier = SesVerifier() if os.environ.get("SES_SENDER") else NoVerifier()
    return _verifier


def set_verifier(v: Verifier | None) -> None:
    """Tests inject a fake; None resets to the default."""
    global _verifier
    _verifier = v
