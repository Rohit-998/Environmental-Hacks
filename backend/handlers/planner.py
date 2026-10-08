"""Scheduled Lambda (06:00 IST): warm one forecast per grid cell, queue one job per school."""
from __future__ import annotations

import datetime as dt
import json
import os

from airday import fanout, obs, secrets
from airday.store import default_store

secrets.load()
_sqs = None


def _enqueue(jobs: list[dict]) -> None:
    global _sqs
    if _sqs is None:
        import boto3

        _sqs = boto3.client("sqs")
    entries = [{"Id": str(i), "MessageBody": json.dumps(j)} for i, j in enumerate(jobs)]
    resp = _sqs.send_message_batch(QueueUrl=os.environ["JOBS_QUEUE_URL"], Entries=entries)
    if resp.get("Failed"):
        raise RuntimeError(f"failed to enqueue {len(resp['Failed'])} jobs: {resp['Failed'][:3]}")


@obs.logger.inject_lambda_context(log_event=False) if obs.ENABLED else (lambda f: f)
@obs.tracer.capture_lambda_handler
@obs.metrics.log_metrics
def handler(event, context):
    date = dt.date.fromisoformat(event["date"]) if isinstance(event, dict) and event.get("date") else fanout.today()
    summary = fanout.plan(default_store(), date, _enqueue)
    obs.count("SchoolsQueued", summary["schools"])
    obs.count("ForecastCellsWarmed", summary["gridCells"])
    obs.logger.info(json.dumps({"event": "daily_plan", **summary}))
    return summary
