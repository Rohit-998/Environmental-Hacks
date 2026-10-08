"""Lambda handler for chat and translation (separate Lambda: bigger package, longer timeout)."""
from __future__ import annotations

from airday import agent, obs, secrets
from handlers.api import respond

secrets.load()


@obs.logger.inject_lambda_context(log_event=False) if obs.ENABLED else (lambda f: f)
@obs.tracer.capture_lambda_handler
@obs.metrics.log_metrics
def handler(event, context):
    return respond(event, extra=agent.ROUTES)
