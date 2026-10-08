"""SQS worker Lambda: builds, stores and emails one school's brief per message.

Partial batch responses: only failed messages return to the queue; after 3 receives they move to the DLQ.
"""
from __future__ import annotations

import json
import os

from airday import fanout, mailer, obs, secrets
from airday import timeutil as tu
from airday.store import default_store

secrets.load()


@obs.logger.inject_lambda_context(log_event=False) if obs.ENABLED else (lambda f: f)
@obs.tracer.capture_lambda_handler
@obs.metrics.log_metrics
def handler(event, context):
    out = fanout.process_batch(default_store(), event.get("Records", []), tu.now_ist(),
                               mailer.configured_sender(), os.environ.get("DASHBOARD_URL", ""))
    for r in out["results"]:
        # This line is the evidence shown in the demo video.
        obs.logger.info(json.dumps(r, ensure_ascii=False))
        if r.get("error"):
            obs.count("BriefFailed")
        elif r.get("skipped"):
            obs.count("BriefSkipped")
        else:
            obs.count("BriefBuilt")
            obs.count("ChangesRecommended", r.get("changes", 0))
            if r.get("email", {}).get("sent"):
                obs.count("EmailSent")
            if r.get("escalated"):
                obs.count("StationEscalations")
    return {"batchItemFailures": out["batchItemFailures"]}
