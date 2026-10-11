# Local platform

Postgres, Redis and Redpanda for local development, run with Docker Compose.

```bash
make up      # start everything, wait until healthy (creates .env on first run)
make ps      # status and health
make psql db=trips
make rpk args="topic list"
make stats   # memory per container
make down    # stop, keep data
make nuke    # stop and delete all data
```

| Service | Image | From the laptop | From other containers |
| --- | --- | --- | --- |
| Postgres | `postgres:18.6-alpine` | `127.0.0.1:5432` | `postgres:5432` |
| Redis | `redis:7.4.11-alpine` | `127.0.0.1:6379` | `redis:6379` |
| Redpanda (Kafka API) | `redpandadata/redpanda:v26.2.4` | `localhost:19092` | `redpanda:9092` |
| Schema Registry | built into Redpanda | `localhost:18081` | `redpanda:8081` |

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

- Every port is bound to `127.0.0.1`, so the databases are not reachable from other machines on the same Wi-Fi.
- Every container has `mem_limit`. The laptop has 7.4 GB of RAM, and a runaway container should be killed rather than freeze the machine.
- Passwords are random, generated into `.env`, which git ignores. `.env.example` documents the variables without secrets.
- Image versions are pinned (`postgres:18.6-alpine`, not `postgres:latest`), so the stack is the same next month and on another machine.

### Native Docker Engine, not Docker Desktop

On Linux, Docker Desktop runs containers inside a virtual machine that reserves memory up front. The native engine runs them directly on the host kernel. The Makefile sets `DOCKER_CONTEXT=default` for this project only, which selects the native engine without changing the laptop's global Docker setting. Run raw `docker` commands the same way: `DOCKER_CONTEXT=default docker ps`.

### Postgres 18 data path

The Postgres 18 image stores data in `/var/lib/postgresql/18/docker`, not `/var/lib/postgresql/data` as earlier versions did. The volume is mounted at `/var/lib/postgresql`, which also leaves room for an in-place `pg_upgrade` to a later major version.
