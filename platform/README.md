# Local platform

Postgres, Redis and Redpanda for local development, plus an optional observability stack (Grafana with Prometheus, Loki and Tempo), run with Docker Compose.

```bash
make up          # start Postgres, Redis, Redpanda; wait until healthy (creates .env on first run)
make obs-up      # also start observability; Grafana on http://localhost:3000
make otel-smoke  # send a test trace, metric and log line; fails if Grafana can't find them
make ps          # status and health
make psql db=trips
make rpk args="topic list"
make stats       # memory per container
make obs-down    # stop observability only, keep its data
make down        # stop everything, keep data
make nuke        # stop everything and delete all data
```

| Service | Image | From the laptop | From other containers |
| --- | --- | --- | --- |
| Postgres | `postgres:18.6-alpine` | `127.0.0.1:5432` | `postgres:5432` |
| Redis | `redis:7.4.11-alpine` | `127.0.0.1:6379` | `redis:6379` |
| Redpanda (Kafka API) | `redpandadata/redpanda:v26.2.4` | `localhost:19092` | `redpanda:9092` |
| Schema Registry | built into Redpanda | `localhost:18081` | `redpanda:8081` |
| Grafana | `grafana/otel-lgtm:0.34.0` | `http://localhost:3000` | `lgtm:3000` |
| OTLP (gRPC / HTTP) | same container | `localhost:4317` / `localhost:4318` | `lgtm:4317` / `lgtm:4318` |

## Design decisions and why

### One Postgres server, one database per service

The plan's first rule is *database per service*: no service reads another service's tables. Locally, one Postgres server holds five databases (`identity`, `trips`, `dispatch`, `pricing`, `payments`) instead of five servers, which saves memory. Location and Realtime have no database; their data lives in Redis or nowhere.

The rule is enforced by Postgres itself, not by convention. `REVOKE ALL ON DATABASE ... FROM PUBLIC` removes the default right of every role to connect, so `trips_app` gets `permission denied for database "payments"`.

### Two roles per service: owner and app

| Role | Used by | Can |
| --- | --- | --- |
| `<service>_owner` | migrations (Django, Alembic) | create, alter and drop tables in its own database |
| `<service>_app` | the running service | read and write rows only (`SELECT, INSERT, UPDATE, DELETE`) |

This is least privilege. If the running service has a SQL-injection bug or a bad deploy, the worst it can do is change rows: it cannot `DROP TABLE` or `ALTER` the schema. `ALTER DEFAULT PRIVILEGES` makes every table the owner creates later usable by the app role automatically, so migrations never need a manual `GRANT`.

The init script passes names and passwords as psql variables (`:"name"` for identifiers, `:'pw'` for strings). psql then quotes them correctly, instead of pasting text into SQL, which is how SQL injection happens.

Verified on day 1: app roles connect only to their own database; app roles can insert and select, but `DROP TABLE` fails with "must be owner", and `CREATE TABLE` fails with "permission denied for schema public".

### Init scripts run once

Files in `docker-entrypoint-initdb.d` run only when the data volume is empty. Changing the script or the passwords in `.env` later has no effect until `make nuke` deletes the volume. For the same reason, the Makefile creates `.env` only when it is missing: overwriting it would leave passwords that no longer match the database.

### Healthchecks and `up --wait`

A running container is not a ready service. Each container has a healthcheck, and `make up` uses `docker compose up --wait`, which returns only when all three report healthy. The Postgres check connects over TCP (`-h 127.0.0.1`): during first-start init, Postgres accepts only socket connections, so the container stays unhealthy until the init script has finished.

### Redis: `noeviction` and no persistence

When Redis reaches `maxmemory` it either deletes keys (eviction) or rejects writes. Dispatch will store driver locks in Redis. If Redis silently evicted a lock, two trips could match one driver. With `noeviction`, a full Redis fails loudly instead. Persistence is off because positions and locks are short-lived; anything that must survive a restart lives in Postgres.

### Redpanda instead of Kafka

Redpanda speaks the Kafka protocol, so the same client libraries work, but it is a single binary without ZooKeeper or a JVM. It idles at about 120 MiB here, much less than a Kafka broker, and includes a Schema Registry.

**Two listeners (advertised listeners).** A Kafka client first asks any broker for the cluster's addresses, then connects to the address the broker *advertises*. Containers must be told `redpanda:9092`, because that name resolves on the Docker network. Programs on the laptop must be told `localhost:19092`, because `redpanda` means nothing there. One listener per audience, each advertising the address its clients can reach:

```
asked on localhost:19092  -> "I am localhost:19092"
asked on redpanda:9092    -> "I am redpanda:9092"
```

Getting this wrong is the classic Kafka-in-Docker bug: the first connection works, then the client is redirected to an address it cannot reach and hangs.

### Security and resource limits

- Every port is bound to `127.0.0.1`, so the databases are not reachable from other machines on the same Wi-Fi. A plain `"5432:5432"` would bind `0.0.0.0` (every network interface). A host firewall such as ufw would not help: Docker writes its own iptables rules for published ports, and that traffic never reaches ufw's rules.
- Every container has `mem_limit`. The laptop has 7.4 GB of RAM, and a runaway container should be killed rather than freeze the machine.
- Passwords are random, generated into `.env`, which git ignores. `.env.example` documents the variables without secrets.
- Image versions are pinned (`postgres:18.6-alpine`, not `postgres:latest`), so the stack is the same next month and on another machine.

### Native Docker Engine, not Docker Desktop

On Linux, Docker Desktop runs containers inside a virtual machine that reserves memory up front. The native engine runs them directly on the host kernel. The Makefile sets `DOCKER_CONTEXT=default` for this project only, which selects the native engine without changing the laptop's global Docker setting. Run raw `docker` commands the same way: `DOCKER_CONTEXT=default docker ps`.

### Postgres 18 data path

The Postgres 18 image stores data in `/var/lib/postgresql/18/docker`, not `/var/lib/postgresql/data` as earlier versions did. The volume is mounted at `/var/lib/postgresql`, which also leaves room for an in-place `pg_upgrade` to a later major version.

## Observability

Decision and alternatives: [ADR-0002](../docs/adr/0002-observability-stack.md).

### One container for all of it

`grafana/otel-lgtm` runs six programs in one container. A service only needs to know one address, the OTLP endpoint; the collector sends each signal where it belongs:

```
service --OTLP--> collector (4317 gRPC, 4318 HTTP)
                    |- traces  -> Tempo
                    |- metrics -> Prometheus
                    |- logs    -> Loki
                                   \- Grafana reads all three (port 3000)
```

Pyroscope (continuous profiling) also runs, because the image's startup script has no switch to turn it off. It uses about 40–70 MiB.

The image is made for development: no high availability, no retention tuning, and every part shares one memory limit. Phase 5 replaces it with the separate tools.

### Started only when needed

The service has the Compose profile `observability`, so `make up` does not start it. It is the biggest container in the stack, and most days only need it while a service is being traced. The Makefile passes the profile to `down`, `ps`, `logs`, `stats` and `nuke`, so those still cover it.

### Grafana plugins turned off to save memory

Grafana starts most data-source plugins as separate processes. Out of the box the container idled at **893 MiB**, about 180 MiB of it plugins this project never uses: MySQL, MSSQL, InfluxDB, OpenTSDB, Elasticsearch, Jaeger, Zipkin, Google Cloud Monitoring and an AI plugin. `GF_PLUGINS_DISABLE_PLUGINS` stops them. After that it idles at **300–580 MiB** in `docker stats`, of which ~330 MiB is process memory and the rest is file cache. The number moves with how much the laptop is swapping.

Grafana usage reports, update checks and plugin auto-updates are off, so nothing phones home and plugins don't change version on their own.

### Grafana has no login

The image lets anyone in as Admin without a password. That is acceptable only because the port is bound to `127.0.0.1`. Never publish port 3000 on `0.0.0.0`.

### The smoke test checks, not just sends

`make otel-smoke` ([otel_smoke.py](otel_smoke.py)) sends one span, one counter and one log line, then queries Tempo, Prometheus and Loki through Grafana until each one appears. It exits 1 if any is missing. A made-up trace id returns 404 and an unknown run id finds no logs, so the checks can fail. Three things it shows that every service will need:

- **Flush before exit.** The SDK batches telemetry. Without `shutdown()`, a short script exits before anything is sent.
- **Logs carry the trace id.** The log line is written inside the span, so Loki stores its `trace_id` and Grafana can jump from a log line to its trace.
- **No ids in metric labels.** Each distinct label value creates a new time series. A run id or trip id as a label would grow Prometheus without limit. Ids go on spans and logs.

Names change on the way in. The counter `smoke_runs` becomes `smoke_runs_total` in Prometheus (counters get `_total`), `service.name` becomes the label `job`, and in Loki it becomes `service_name`.
