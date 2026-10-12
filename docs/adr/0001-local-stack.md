# ADR-0001: Local development stack

- **Status:** Accepted
- **Date decided:** 2026-10-11 (written up 2026-10-12)
- **Related:** [Day 1 log](../daily/day-001-2026-10-11.md), [platform/README.md](../../platform/README.md), [platform/compose.yaml](../../platform/compose.yaml)

## Context

RideMesh runs entirely on one laptop until the Kubernetes phase, and Kubernetes (kind) will also run on that laptop. The plan assumes 16 GB of RAM, Python 3.12 and Postgres 16.

The laptop:

| Resource | Value |
| --- | --- |
| RAM | 7.4 GiB total; 6.4 GiB already in use by the desktop, browser and VS Code before anything starts |
| Swap | 14 GiB; 11 GiB in use on 2026-10-12, with no containers running |
| CPU | 12 cores |
| Free disk | 165 GB |
| Docker | Native Docker Engine and Docker Desktop are both installed; the default CLI context pointed at Docker Desktop |
| Python | Miniconda `base` auto-activates in every terminal |

**Memory is the hard limit**, not CPU or disk. Every container added later competes for about 1 GiB of free RAM. Before this stack there are Postgres, Redis and a Kafka-compatible broker; after it come an observability stack, seven services, two web apps and a load generator.

## Decision

| Area | Choice | Plan said | Why |
| --- | --- | --- | --- |
| Python | 3.13, uv-managed, in `.venv`, pinned in `.python-version` | 3.12 | Already installed through uv, and the planned libraries support it. A uv-managed interpreter is not touched by Conda updates. |
| Python tooling | uv workspace (`services/*`); ruff, mypy strict, pytest, pre-commit | same | One lock file for the repo; every service is still its own package. |
| Postgres | `postgres:18.6-alpine`: **one server**, one database per service | 16 | Built-in `uuidv7()` (time-ordered IDs, useful for `trip_events` and the capstone); the local `psql` client is 18. One server instead of five saves memory. |
| Database isolation | Two roles per service: `<svc>_owner` runs migrations, `<svc>_app` reads and writes rows; `REVOKE ALL ... FROM PUBLIC` on each database | not specified | Database per service is enforced by Postgres permissions, not by convention. The running app cannot `DROP` or `ALTER` tables. |
| Redis | `redis:7.4.11-alpine`, `maxmemory 200mb`, `noeviction`, no persistence | Redis 7 | An evicted driver lock means a double-matched driver, so a full Redis must reject writes. The data is short-lived, so persistence is off. |
| Kafka API | `redpandadata/redpanda:v26.2.4`, one node, `--smp 1 --memory 512M`, dev-container mode | Redpanda | Same Kafka protocol and client libraries, no JVM and no ZooKeeper, Schema Registry built in. |
| Container runtime | Native Docker Engine (`DOCKER_CONTEXT=default` set in the Makefile only) | not specified | Docker Desktop on Linux runs a VM that reserves memory up front. |
| Network | Every port bound to `127.0.0.1` | not specified | The databases cannot be reached from the Wi-Fi. Docker's iptables rules bypass ufw, so a firewall would not protect a `0.0.0.0` port. |
| Resource limits | `mem_limit` on every container: Postgres 512 MiB, Redis 256 MiB, Redpanda 768 MiB (1.5 GiB in total) | not specified | A runaway container is killed instead of freezing the laptop. |
| Versions | Exact image tags, never `latest` | not specified | The stack is the same next month and on another machine. |

**Rule for later containers:** each new container gets a `mem_limit`, and its idle memory is measured with `make stats` and written in the daily log before it is accepted.

### Measured

| What | Value |
| --- | --- |
| Idle memory, all three (2026-10-11) | ~178 MiB: Postgres 45, Redis 11, Redpanda 122 |
| Idle memory after a fresh start (2026-10-12) | Postgres 39 MiB, Redpanda 182 MiB |
| `make up` to all healthy, images already pulled | 29 s |
| Postgres `max_connections` / `shared_buffers` | 100 / 128 MB (image defaults) |

## Alternatives considered

| Option | Why not |
| --- | --- |
| Apache Kafka in KRaft mode | A JVM broker uses several times more memory than Redpanda. The protocol is the same, so moving to Kafka (Strimzi) in Phase 5 needs no client changes. |
| Postgres 16, as in the plan | Works, but `uuidv7()` would need an extension or app-side code. |
| One Postgres server per service | Full isolation, but about five times the memory. Separate databases plus role permissions already give "no service reads another's tables". |
| Docker Desktop | Its VM reserves memory that this laptop doesn't have. |
| Conda's Python | A `conda update` can change the interpreter under the project. |
| Redis with `allkeys-lru` | Tested on Day 1: in a small Redis, 599 keys were deleted silently, including the driver lock. |
| Redis with AOF or RDB persistence | Extra disk writes for data that is meant to expire anyway. |

## Consequences

**Gets easier:**

- The core stack idles at about 180–230 MiB, which leaves room for observability and the services.
- Cross-service database access fails with a permission error, so the "database per service" rule cannot be broken by accident. Tested on Day 1.
- The same pinned versions run on any machine, and `make up` returns only when everything is healthy.

**Gets harder, or risks we accept:**

- **One Postgres server is shared.** A slow query or a connection leak in one service affects all five databases, and the 100-connection limit is shared too. This is backend problem 9 (connection exhaustion), and it may show up before Phase 5.
- **Redpanda dev-container mode is not durable.** Verified on 2026-10-12: it runs with `--unsafe-bypass-fsync=true` and `write_caching_default = true`, so a crash can lose acknowledged messages. Never use this setup to judge durability.
- **Topics are created automatically** (`auto_create_topics_enabled = true`). A typo in a topic name creates a new, empty topic instead of failing. Create topics explicitly, and turn auto-create off before the event catalog is used for real (Phase 1).
- **One broker, replication factor 1.** Broker failover and under-replicated partitions cannot be reproduced locally. Consumer-side problems (lag, rebalances, duplicate delivery) still can.
- **Postgres 18 is newer than the plan.** Some guides and tools assume 16. The data directory has already moved (`/var/lib/postgresql/18/docker`).
- **Memory stays the bottleneck.** The laptop already swaps before the stack starts, so slow tests can be the laptop's fault rather than the code's. Close other apps before measuring, and note the free memory next to every number.
- All service roles share one dev password locally. Each gets its own Secret in Kubernetes (Phase 5).

## Revisit when

- **Phase 5 (Kubernetes):** a Postgres per service or an operator such as CloudNativePG, Redpanda or Strimzi with three brokers, and separate secrets.
- A phase needs broker replication or durability tests: run a three-node cluster with fsync on, just for that test.
- Idle memory of the whole stack no longer fits next to the editor and the browser: switch the observability stack to Grafana Cloud, or stop the services not in use.
- A required library has no Python 3.13 support.
