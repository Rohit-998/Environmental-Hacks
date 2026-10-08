"""Loads secrets from SSM Parameter Store into env vars, once per Lambda cold start.

    ADMIN_KEY_PARAM    -> ADMIN_KEY
    DATA_GOV_KEY_PARAM -> DATA_GOV_API_KEY
    OPENAQ_KEY_PARAM   -> OPENAQ_API_KEY

A missing parameter is logged and skipped; the feature that needs it reports "not configured".
Locally, set the target env vars directly and nothing is fetched.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("airday")

MAPPING = {
    "ADMIN_KEY_PARAM": "ADMIN_KEY",
    "DATA_GOV_KEY_PARAM": "DATA_GOV_API_KEY",
    "OPENAQ_KEY_PARAM": "OPENAQ_API_KEY",
}
_loaded = False


def load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    wanted = {os.environ[p]: target for p, target in MAPPING.items()
              if os.environ.get(p) and not os.environ.get(target)}
    if not wanted:
        return
    import boto3

    resp = boto3.client("ssm").get_parameters(Names=list(wanted), WithDecryption=True)
    for p in resp.get("Parameters", []):
        os.environ[wanted[p["Name"]]] = p["Value"]
    for name in resp.get("InvalidParameters", []):
        log.warning("SSM parameter %s not found; %s stays unset", name, wanted[name])
