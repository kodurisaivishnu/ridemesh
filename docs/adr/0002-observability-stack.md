# ADR-0002: Observability stack

- **Status:** Accepted
- **Date decided:** 2026-10-12
- **Related:** [ADR-0001](0001-local-stack.md), [Day 2 log](../daily/day-002-2026-10-12.md), [platform/README.md](../../platform/README.md#observability)

## Context

The Phase 0 exit check is "a request through Traefik to each framework shows as one trace in Grafana". The plan's rule "no numbers, no done" needs metrics and dashboards from the first service on. Logs have to be searchable next to the traces.

The plan lists five separate tools: an OpenTelemetry collector, Prometheus, Loki, Tempo and Grafana. ADR-0001 records that memory is the hard limit on this laptop. On 2026-10-12, with Chrome and VS Code open and no containers running, 1.1 GiB of RAM was available and 13.2 of 14.9 GiB of swap was in use.

## Decision

| Area | Choice | Why |
| --- | --- | --- |
| Stack | `grafana/otel-lgtm:0.34.0`: collector, Prometheus, Loki, Tempo, Pyroscope and Grafana in one container | One container, one endpoint, configured out of the box. Same tools as the plan, so queries and dashboards carry over to Phase 5. |
| When it runs | Compose profile `observability`: `make obs-up` starts it, `make up` does not | It is the largest container in the stack. Run it only while tracing or measuring. |
| How services send data | OTLP over HTTP/protobuf to port 4318 (`lgtm:4318` from containers, `localhost:4318` from the laptop) | The OpenTelemetry default protocol, and it avoids the large `grpcio` package in every Python service. |
| Grafana plugins | Unused data-source plugins disabled with `GF_PLUGINS_DISABLE_PLUGINS`; Prometheus, Loki, Tempo and Pyroscope kept | Idle memory fell from 893 MiB to 300–580 MiB. |
| Phoning home | Grafana usage reports, update checks and plugin auto-updates off | No data sent to grafana.com; plugins stay at the version first installed. |
| Limits | `mem_limit: 1g`, ports bound to `127.0.0.1`, data in the `lgtm-data` volume | Same rules as every other container (ADR-0001). |
| Proof it works | `make otel-smoke` sends a span, a counter and a log line, then queries each through Grafana; exits 1 if one is missing | A check that can fail, not "open Grafana and look". |

### Measured

| What | Value |
| --- | --- |
| Image size on disk | 2.7 GB |
| `make obs-up` to healthy (image pulled) | 11 s first start, 6 s on restart |
| Idle memory, defaults | 893 MiB |
| Idle memory, unused plugins disabled | 300–580 MiB in `docker stats`; ~330 MiB process memory, the rest file cache |
| Largest processes (RSS) | Grafana 106–132, collector 65–71, Pyroscope 60–77, Loki 40–55, Tempo 21–46, Prometheus 33–39 MiB |
| Whole stack idle (core + observability), two samples | ~670 MiB |
| Smoke test: send, then find all three signals | under 3 s |

## Alternatives considered

| Option | Why not |
| --- | --- |
| The plan's five separate containers | The same programs plus five containers' worth of configuration to write and keep in sync. Teaches more wiring, but that is Phase 5 work. It doesn't save memory either. |
| Grafana Cloud free tier | Uses no local RAM. But data leaves the laptop, it needs an account and a token, load tests depend on the internet and on free-tier limits, and it is a different setup from what Phase 5 runs on Kubernetes. Kept as the fallback if local memory runs out. |
| Jaeger all-in-one | Light, but traces only. Metrics and logs are needed too. |
| No observability until Phase 1 | The Phase 0 exit check needs traces in Grafana, and every Phase 1 load test needs dashboards. |

## Consequences

**Gets easier:**

- A service needs one setting, the OTLP endpoint, to send all three signals.
- Logs written inside a span carry its trace id, so Grafana jumps from a log line to the trace (checked by the smoke test).
- `make otel-smoke` tells in seconds whether the pipeline works. Run it first when a service's telemetry goes missing.

**Gets harder, or risks we accept:**

- **Development image.** No high availability and no retention tuning. The component versions are fixed by the image, so Tempo cannot be upgraded on its own.
- **One memory limit for six programs.** If the container reaches 1 GiB, the kernel kills one process inside it and the healthcheck turns unhealthy. Under load tests, watch `make stats`.
- **Pyroscope runs and isn't used yet** (40–70 MiB). The image's startup script has no switch for it.
- **Grafana has no login** (anonymous Admin). This is safe only while the port stays on `127.0.0.1`.
- **Memory is tighter.** The whole stack idles at ~670 MiB while the laptop is already swapping. Stop observability (`make obs-down`) when it isn't needed.
- **The collector config comes from the image.** Changes such as tail sampling or dropping noisy spans mean mounting our own `otelcol-config.yaml`.

## Revisit when

- **Phase 5 (Kubernetes):** separate collector, Prometheus, Loki, Tempo and Grafana, each with its own limits and retention.
- The container hits its memory limit during a load test: raise the limit, or move traces and logs to Grafana Cloud.
- The laptop can't run services, the stack and a browser together: switch to Grafana Cloud free.
- We need collector processing (sampling, filtering, extra exporters): mount our own collector config.
