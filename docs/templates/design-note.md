<!--
Copy to docs/design/<service>.md and fill it in before the service's first line of code.
Half a page is enough. Update it when the design changes; it describes what is true now.
-->

# Design note: <Service>

- **Framework:** Django | FastAPI | Flask, and why it fits this service
- **Layer:** edge | product | platform (calls go downward only)
- **Status:** Draft | Built | Changed on YYYY-MM-DD

## Responsibilities

What this service does, in 2–4 bullets. Also what it does **not** do, if another service could be confused with it.

## Owned data

| Store | What | Notes |
| --- | --- | --- |
| Postgres `<db>` | tables | biggest table, expected growth |
| Redis | keys and TTLs | what happens if they are lost |

No other service reads or writes this data directly.

## APIs (synchronous)

| Endpoint | Caller | Purpose | Idempotent? |
| --- | --- | --- | --- |
| `POST /…` | | | `Idempotency-Key` |

## Calls it makes

| To | Why the caller must wait | Timeout | Retries | If it fails |
| --- | --- | --- | --- | --- |
| | | | | fallback or error |

## Events

| Publishes | Consumes | Partition key | What it does on a duplicate |
| --- | --- | --- | --- |
| `entity.verb` v1 | | trip id | |

## Failure modes

| What breaks | What the user sees | How we detect it | What the service does |
| --- | --- | --- | --- |
| Its database is down | | | |
| A dependency is slow | | | |
| The same event arrives twice | | | |
| The pod is killed mid-request | | | |

## Numbers to watch

- Expected load (rps, events/s) and the latency target (p95/p99).
- The dashboard panels this service adds.

## Open questions

-
