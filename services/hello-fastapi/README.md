# hello-fastapi

Phase 0 hello service: one FastAPI route behind Traefik, traced with OpenTelemetry. Throwaway; the real FastAPI services (Realtime, Location, Dispatch) start in Phase 1 from what it teaches. Decisions: [ADR-0004](../../docs/adr/0004-service-skeleton-and-gateway.md).

| Route | Returns |
| --- | --- |
| `GET /hello` | `{"service": "hello-fastapi", "message": "hello", "time": "<UTC ISO 8601>"}`, and logs `said hello` |
| `GET /healthz` | `{"status": "ok"}`; used by the healthcheck, left out of traces |

## Run it in the stack (traced)

```bash
make hello-up                       # builds the image; starts lgtm, Traefik and this service
curl localhost:8080/fastapi/hello   # through Traefik; the service has no published port
make trace-check                    # proves Traefik and this service share one trace
make logs s=hello-fastapi           # each "said hello" line shows its trace_id
```

## Run it on the laptop

While coding, without tracing, reloading on save:

```bash
uv run uvicorn hello_fastapi.api.app:app --reload
```

With tracing, to check the OpenTelemetry settings without Docker or Traefik (`make obs-up` first):

```bash
OTEL_SERVICE_NAME=hello-fastapi OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
OTEL_PYTHON_LOG_CORRELATION=true OTEL_PYTHON_FASTAPI_EXCLUDED_URLS=healthz \
uv run opentelemetry-instrument uvicorn hello_fastapi.api.app:app
```

The exporter's default endpoint, `http://localhost:4318`, is the `lgtm` container's published port.

## Test

```bash
uv run pytest services/hello-fastapi
```

## How the tracing works

There is no OpenTelemetry code in `src/`. The container's command is `opentelemetry-instrument uvicorn ...`, which, before the app is imported:

1. starts the SDK and the OTLP exporters (`opentelemetry-distro`),
2. loads every installed instrumentation: FastAPI (a server span per request, continuing an incoming `traceparent`) and logging (log records to Loki, with the trace id),
3. reads its settings from the `OTEL_*` variables in `platform/compose.yaml`.

So the same setup works for Django and Flask with their own instrumentation package. Two things it cannot do without code: hide the ASGI `http send` child spans, and run under `--workers` or `--reload`, which start child processes.
