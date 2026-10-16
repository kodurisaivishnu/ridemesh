"""Check that a request through Traefik shows up in Tempo as one trace across two services.

Sends GET <path> to Traefik with a traceparent header made here, so the trace id is known
before Tempo has it. Then asks Tempo (through Grafana) for that trace until it holds a
server span of the service whose parent is a Traefik span. Exits 1 otherwise.

    make hello-up && make trace-check        # /fastapi/hello
    make trace-check path=/django/hello      # another route

The service is named after the path's first segment: /fastapi/... -> hello-fastapi.
"""

import os
import secrets
import sys
import urllib.request
from typing import Any
from urllib.error import URLError

from otel_smoke import GRAFANA, query, wait_for

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:8080")

Spans = dict[str, list[dict[str, Any]]]


def spans_by_service(trace: dict[str, Any]) -> Spans:
    """Tempo's OTLP JSON flattened to {service.name: [span, ...]}."""
    result: Spans = {}
    for resource_spans in trace.get("resourceSpans", []):
        attributes = resource_spans["resource"]["attributes"]
        service = next(a["value"]["stringValue"] for a in attributes if a["key"] == "service.name")
        for scope_spans in resource_spans.get("scopeSpans", []):
            result.setdefault(service, []).extend(scope_spans.get("spans", []))
    return result


def joined(spans: Spans, service: str) -> bool:
    """True when a server span of `service` is the child of a Traefik span.

    That link exists only if Traefik passed its traceparent on and the service used it.
    Two separate traces, or one trace without the link, both fail.
    """
    traefik_span_ids = {span["spanId"] for span in spans.get("traefik", [])}
    return any(
        span.get("kind") == "SPAN_KIND_SERVER" and span.get("parentSpanId") in traefik_span_ids
        for span in spans.get(service, [])
    )


def check(path: str) -> bool:
    service = "hello-" + path.strip("/").split("/")[0]
    trace_id = secrets.token_hex(16)
    # W3C trace context: version-traceid-parentid-flags. Flags 01 = sampled: record this one.
    headers = {"traceparent": f"00-{trace_id}-{secrets.token_hex(8)}-01"}
    try:
        request = urllib.request.Request(GATEWAY + path, headers=headers)  # noqa: S310 (http URL)
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            print(f"GET {path} -> {response.status}, trace id {trace_id}")
    except URLError as error:  # also HTTPError: 404 unknown route, 502 service down, ...
        print(f"GET {path} -> {error}")
        return False

    spans: Spans = {}

    def found() -> bool:
        nonlocal spans
        # Tempo answers 200 with an empty trace until the spans arrive (batched every few s).
        response = query(f"tempo/api/v2/traces/{trace_id}") or {}
        spans = spans_by_service(response.get("trace", {}))
        return joined(spans, service)

    ok = wait_for(f"traefik -> {service}", found)
    counts = ", ".join(f"{name} {len(s)}" for name, s in sorted(spans.items())) or "none"
    print(f"  spans per service: {counts}")
    return ok


def main() -> int:
    paths = sys.argv[1:] or ["/fastapi/hello"]
    print(f"Through Traefik at {GATEWAY}; Tempo through Grafana at {GRAFANA}")
    results = [check(path) for path in paths]
    print("\nTo see one: Grafana → Explore → Tempo → paste the trace id")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
