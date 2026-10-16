# ADR-0004: Service skeleton and gateway

- **Status:** Accepted
- **Date decided:** 2026-10-15
- **Related:** [ADR-0001](0001-local-stack.md), [ADR-0002](0002-observability-stack.md), [ADR-0003](0003-frameworks.md), [Day 3 log](../daily/day-003-2026-10-13.md), [platform/README.md](../../platform/README.md#gateway-traefik)

## Context

Seven services in three frameworks (ADR-0003) need the same answers: where the code lives, how its dependencies are locked and installed, how it is traced, how it runs, and how requests reach it. Choosing once, on the first hello service, keeps all seven the same.

Facts that shape the choice:

- **Phase 0 exit check:** one request through the gateway to each framework shows as one trace in Grafana (ADR-0002). Each framework has its own instrumentation package, so the tracing setup should not depend on the framework.
- **Memory** is the hard limit (ADR-0001: 7.4 GiB RAM, the laptop already swapping).
- **The plan** says: "API gateway: Traefik (simple) or Kong (closer to industry); JWT validation at the edge, rate limits, routing." Phase 5 runs on k3s, which ships Traefik as its built-in ingress.
- Measured on Day 3 with `hello-fastapi`: image 146 MB; idle process memory Traefik 24 MiB, hello-fastapi 47 MiB; Traefik adds ~1 ms at p50 and ~2 ms at p95 per request.

## Decision

**Service skeleton**

- Each service is `services/<name>/`, its own package (`pyproject.toml`, `uv_build`, code in `src/<package>/`), and a member of the uv workspace. One `uv.lock` at the root pins every service's dependencies.
- Every service is also in the root `dev` dependency group, so `uv sync` installs it editable into the root `.venv`, where pytest and mypy (pre-commit) can import it.
- Hello services use only `api/`. Real services (Phase 1) use the plan's four layers, `domain/`, `application/`, `adapters/`, `api/`, with the framework only in `api/` and `adapters/` (ADR-0003).

**Tracing: zero-code**

- We use `opentelemetry-instrument` to wrap the server process, and `OTEL_*` environment variables in Compose to configure it. Service code has no OpenTelemetry imports. Django and Flask use the same wrapper and the same variables; only the instrumentation package differs.
- Instrumentation packages are dependencies in the service's `pyproject.toml`, never installed by `opentelemetry-bootstrap` at build time, so `uv.lock` pins them.
- Logs: `opentelemetry-instrumentation-logging` sends Python log records to Loki. `OTEL_PYTHON_LOG_CORRELATION=true` also prints them to stderr with the trace id. The SDK's own switch (`OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED`) is deprecated in SDK 1.45.
- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`: the distro defaults to gRPC, but only the HTTP exporter is installed (ADR-0002).
- The health endpoint is excluded from traces (`OTEL_PYTHON_<FRAMEWORK>_EXCLUDED_URLS=healthz`).

**How it runs**

- In a container from Compose, behind a profile (`hello` for now), started by `make hello-up`. Multi-stage Dockerfile: uv installs exactly the locked packages of one service (`uv sync --frozen --no-dev --package <name> --no-editable`) into a venv, and the runtime stage gets only that venv on the same `python:3.13.16-slim-trixie` base. It runs as a non-root user. The build context is the repo root, and `.dockerignore` is an allowlist.
- One server process per container: no `--workers`, no `--reload` (zero-code instrumentation does not support child processes). Scale with more containers, not more workers.
- Services publish **no ports**. They are reachable only on the Compose network, through the gateway.
- While coding: `uv run uvicorn ... --reload` on the laptop, without tracing.

**Gateway: Traefik v3.7, file provider**

- Traefik is the single way in, on `127.0.0.1:8080`; the dashboard on `127.0.0.1:8081`.
- Routes are YAML files in `platform/traefik/dynamic/`, reloaded on save. One router per service, `PathPrefix(`/<name>/`)` plus a `stripPrefix` middleware, so services don't know their public prefix.
- Traefik's built-in OpenTelemetry tracing sends spans to `lgtm:4318`, and the W3C `traceparent` header it adds to each forwarded request makes the service's spans children of Traefik's.
- Hardening from day one: runs as uid 65534, no Docker socket, `aliasHeadersStrategy: delete` on `web`, no version checks or usage stats.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Tracing set up in code (SDK, as in `otel_smoke.py`) | More control (e.g. hiding the ASGI `http send` spans), but three versions of the same setup code, one per framework, to keep in step. Zero-code gives one setup for all three. Revisit if a framework needs something only code can do. |
| `opentelemetry-bootstrap -a install` in the Dockerfile | Installs whatever versions are newest at build time, outside `uv.lock`: two builds of the same commit can differ. |
| Traefik Docker provider (container labels) | Routes would live next to each service in `compose.yaml`, but Traefik would need `/var/run/docker.sock`, which gives root on the laptop even read-only. Routes in files are one more place to edit, which is fine for seven services. |
| Kong | Closer to what many companies run, with JWT and rate-limit plugins built in. But it is heavier (Nginx + Lua, and a database or a declarative config) where Traefik idles at 24 MiB, and Phase 5's k3s ships Traefik as its ingress, so one gateway works locally and in Kubernetes. |
| Publish each service's port too | Easier to curl, but then a client can skip the gateway, and with it everything the gateway will enforce (JWT, rate limits). |
| `uv sync --all-packages` instead of listing services in the root dev group | Works, but a plain `uv sync` (which removes what the root does not list) would uninstall the services, and pre-commit's mypy would fail on a fresh clone. |

## Consequences

**Gets easier:**

- Days 4 and 5 copy the pattern: a new service is a `pyproject.toml`, a Dockerfile, a Compose entry with the same `OTEL_*` variables, and one router in `dynamic/`. `make trace-check path=/<name>/hello` proves it joined the trace.
- Every request has a single entry point, which is where JWT, rate limits and request ids will go in Phase 1 and Phase 4.
- Route changes need no restart.

**Gets harder, or risks we accept:**

- **JWT validation is not in open-source Traefik** (the JWT middleware is Traefik Hub only). JWT at the edge will need `ForwardAuth` to Identity or a plugin. Decide in Phase 1.
- **Traefik trusts any incoming `traceparent`.** A client can choose its own trace id and force sampling. That is useful for `trace-check`, but a public edge should start a new trace, or at least ignore the client's sampled flag. Revisit before Phase 5.
- Zero-code keeps two ASGI `http send` spans per FastAPI request; hiding them needs code.
- One process per container limits concurrency to one event loop (FastAPI). Django and Flask normally run under gunicorn, which forks worker processes, and forking is what zero-code instrumentation handles badly. Day 4 checks this first.
- Traefik adds ~1 ms at p50 and ~2 ms at p95 per request on this laptop. Fine for this project. Measure again under load.
- The `lgtm` container was at 972 MiB of its 1 GiB limit (507 MiB process memory) after Day 3's traces. Watch it as Days 4–5 add services.

## Revisit when

- A framework's spans cannot join the Traefik trace with zero-code instrumentation by Day 5.
- Phase 1 needs JWT at the edge and ForwardAuth adds too much latency: compare a plugin, or Kong.
- Phase 5 moves to k3s: routes become Ingress or IngressRoute resources instead of files.
- The edge is exposed beyond the laptop: stop trusting incoming trace context.
