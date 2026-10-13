# ADR-0003: Three Python frameworks

- **Status:** Accepted
- **Date decided:** 2026-10-13
- **Related:** [ADR-0001](0001-local-stack.md), [ADR-0002](0002-observability-stack.md), [Day 2 log](../daily/day-002-2026-10-12.md)

## Context

RideMesh has seven services with very different jobs. Some are transactional state machines with an admin UI. Some hold thousands of long-lived WebSocket connections. Some are small stateless calculators. The plan proposes three frameworks, each where its strengths fit. The question has been open since Day 1, and it must be settled before Day 3 writes the first hello service.

Three facts shape the choice:

- **Memory is the hard limit** (ADR-0001). Memory depends on the number of service processes and workers, not on how many frameworks they use.
- **The Phase 0 exit check** is one trace through Traefik to each framework, so every framework must be wired into OpenTelemetry (ADR-0002).
- **The plan asks for the same layout in every service:** `domain/`, `application/`, `adapters/`, `api/`, with the framework only in `api/` and `adapters/`.

## Decision

We use three frameworks, mapped as in the plan:

| Service | Framework | Why this one |
| --- | --- | --- |
| Identity | Django + DRF | Auth, driver onboarding and an ops admin come almost free with Django admin |
| Trips | Django + DRF | Transactional state machine, ORM, migrations and admin; holds `trip_events`, the table the capstone migrates |
| Realtime gateway | FastAPI | Thousands of long-lived WebSockets need async I/O |
| Location | FastAPI | Async GPS stream in, "drivers near a point" out in milliseconds |
| Dispatch | FastAPI | Async calls to Location and Pricing inside a latency-critical matching loop |
| Pricing | Flask | Small and stateless; Flask keeps it tiny |
| Payments | Flask + SQLAlchemy + Alembic | Idempotent charge API and double-entry ledger; a second ORM and migration tool to learn beside Django's |

**Rule that keeps three frameworks manageable:** framework code stays in `api/` and `adapters/`. `domain/` and `application/` never import Django, FastAPI or Flask, so business rules look and test the same in every service.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Two: Django + FastAPI (Pricing and Payments on FastAPI) | Less to learn and one fewer framework to trace. But it loses Flask's "small sync service" case and the "shared contracts across different frameworks" story the plan builds on. SQLAlchemy and Alembic could still be learned, so this was the closest alternative. |
| FastAPI everywhere | One way to do everything, but no ORM admin. Identity and Trips would rebuild what Django gives for free, and Django's migrations, the subject of data problem 1, would never be learned. |
| Django everywhere | Async WebSockets at the Realtime gateway are possible with Channels, but harder and heavier than FastAPI for thousands of sockets. |

## Consequences

**Gets easier:**

- Each service uses the tool that fits it, which is a realistic team choice and a strong interview answer to "why three frameworks, and what did each cost?".
- Two ORMs and two migration tools (Django, SQLAlchemy/Alembic) show up in the data problems, so migration-safety lessons are learned twice from different angles.
- Services can only talk through contracts (OpenAPI, JSON Schema events), never shared code. This enforces the microservice rules the plan sets.

**Gets harder, or risks we accept:**

- **Three OpenTelemetry setups.** Each framework has its own instrumentation package, so tracing has to be checked three times. Days 3–5 exist for exactly this.
- **Three ways to generate OpenAPI.** FastAPI has it built in; Django needs a library such as drf-spectacular, and Flask one such as flask-smorest.
- **Two server models.** Django and Flask run under a sync WSGI server with worker processes (gunicorn); FastAPI runs under an async ASGI server (uvicorn). Each worker is a separate process with its own memory, so keep worker counts low locally and measure each hello service with `make stats`.
- **Shared Python code must not depend on any framework** (settings, logging and OTel setup, event schemas). Otherwise one framework's quirks leak into all seven services.
- More to learn in Phase 0 and Phase 1, before any feature work.

## Revisit when

- A hello service for one framework cannot join the shared trace by Day 5: fix it or drop that framework before Phase 1 starts.
- The laptop cannot run all seven services together: run fewer at once, or lower worker counts. This is a service-count problem, not a framework one.
- Pricing or Payments needs async I/O that Flask makes awkward.
