"""Smoke test for the observability stack.

Sends one span, one counter and one log line over OTLP, then queries Grafana's data sources
until each one shows up. Exits 1 if any is missing after TIMEOUT_S seconds.

    make obs-up && make otel-smoke
"""

import json
import logging
import os
import time
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any
from urllib.error import URLError

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import format_trace_id

SERVICE = "otel-smoke"
GRAFANA = os.environ.get("GRAFANA_URL", "http://localhost:3000")
TIMEOUT_S = 60


def send(run_id: str) -> str:
    """Send the three signals, flush them, and return the trace id."""
    resource = Resource.create({"service.name": SERVICE})

    # The exporters read OTEL_EXPORTER_OTLP_ENDPOINT (default http://localhost:4318).
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    meter_provider = MeterProvider(
        resource=resource, metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())]
    )
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))

    log = logging.getLogger(SERVICE)
    log.addHandler(LoggingHandler(logger_provider=logger_provider))
    log.setLevel(logging.INFO)

    # No run id on the counter: each distinct label value is a new time series, so ids in
    # metric labels blow up Prometheus. Ids belong on spans and logs.
    runs = meter_provider.get_meter(SERVICE).create_counter("smoke_runs")
    tracer = tracer_provider.get_tracer(SERVICE)
    with tracer.start_as_current_span("smoke-test") as span:
        span.set_attribute("smoke.run_id", run_id)
        runs.add(1)
        # Logged inside the span, so the record carries the trace id and Loki can link to Tempo.
        log.info("smoke test run %s", run_id)
        trace_id = format_trace_id(span.get_span_context().trace_id)

    # Shutdown flushes the batches; without it the process exits before anything is sent.
    tracer_provider.shutdown()
    meter_provider.shutdown()
    logger_provider.shutdown()
    return trace_id


def query(path: str, params: dict[str, str] | None = None) -> Any:
    """GET through Grafana's data source proxy. None when not found (yet)."""
    url = f"{GRAFANA}/api/datasources/proxy/uid/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 (http URL built above)
            return json.load(resp)
    except URLError:
        return None


def has_results(response: Any) -> bool:
    return bool(response and response["data"]["result"])


def wait_for(name: str, found: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        if found():
            print(f"  {name:<11} found")
            return True
        time.sleep(2)
    print(f"  {name:<11} NOT FOUND after {TIMEOUT_S} s")
    return False


def main() -> int:
    run_id = uuid.uuid4().hex[:8]
    print(f"Sending a span, a counter and a log line (run {run_id})")
    trace_id = send(run_id)

    metric_query = f'smoke_runs_total{{job="{SERVICE}"}}'
    log_query = f'{{service_name="{SERVICE}"}} |= "{run_id}"'
    print(f"Looking for them through Grafana at {GRAFANA}")
    results = [
        wait_for("Tempo", lambda: query(f"tempo/api/traces/{trace_id}") is not None),
        wait_for(
            "Prometheus",
            lambda: has_results(query("prometheus/api/v1/query", {"query": metric_query})),
        ),
        wait_for(
            "Loki",
            lambda: has_results(query("loki/loki/api/v1/query_range", {"query": log_query})),
        ),
    ]

    print("\nTo see them in Grafana → Explore:")
    print(f"  Tempo       trace id {trace_id}")
    print(f"  Prometheus  {metric_query}")
    print(f"  Loki        {log_query}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
