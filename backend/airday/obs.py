"""Observability: Powertools for AWS Lambda (AWS open source) for structured logs, X-Ray traces and
CloudWatch EMF metrics.

Locally (no POWERTOOLS_SERVICE_NAME) everything degrades to plain logging and no-op metrics, so tests and the
dev server don't need AWS.
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Iterator

NAMESPACE = os.environ.get("POWERTOOLS_METRICS_NAMESPACE", "AirDay")
ENABLED = bool(os.environ.get("POWERTOOLS_SERVICE_NAME"))

if ENABLED:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    logger = Logger()
    tracer = Tracer()
    metrics = Metrics(namespace=NAMESPACE)
else:  # pragma: no cover - local fallbacks
    logger = logging.getLogger("airday")

    class _NoTracer:
        def capture_lambda_handler(self, fn=None, **_):
            return fn if fn else (lambda f: f)

        def capture_method(self, fn=None, **_):
            return fn if fn else (lambda f: f)

        @contextlib.contextmanager
        def provider_subsegment(self, name: str) -> Iterator[None]:  # noqa: ARG002
            yield None

        def put_annotation(self, *_: Any, **__: Any) -> None:
            pass

    class _NoMetrics:
        def log_metrics(self, fn=None, **_):
            return fn if fn else (lambda f: f)

        def add_metric(self, *_: Any, **__: Any) -> None:
            pass

        def add_dimension(self, *_: Any, **__: Any) -> None:
            pass

    class MetricUnit:  # type: ignore[no-redef]
        Count = "Count"
        Milliseconds = "Milliseconds"

    tracer = _NoTracer()  # type: ignore[assignment]
    metrics = _NoMetrics()  # type: ignore[assignment]


def count(name: str, value: float = 1) -> None:
    metrics.add_metric(name=name, unit=MetricUnit.Count, value=value)


def annotate(**kv: Any) -> None:
    """X-Ray annotations are indexed, so traces can be searched by school or date."""
    for k, v in kv.items():
        tracer.put_annotation(key=k, value=v)
