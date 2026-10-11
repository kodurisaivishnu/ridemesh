# RideMesh

A ride-hailing platform in the style of Uber, built to learn how production systems fail and how to fix them.

**Work in progress.** Currently in Phase 0 (Foundations), started 11 Oct 2026. Daily progress is in [docs/daily/](docs/daily/).

## Goal

- 7 Python microservices (Django, FastAPI, Flask), each with its own Postgres database
- Kafka-compatible events (Redpanda), Redis with an H3 geo index
- React + TypeScript rider and driver web apps with live maps
- OpenTelemetry metrics, logs and traces for every service; Kubernetes deployment
- A traffic simulator that drives thousands of fake drivers and riders, so that real failures show up
- Each failure reproduced under load, fixed, measured before and after, and written up in [docs/incidents/](docs/incidents/)

## Layout

| Path | Contents |
| --- | --- |
| `services/` | Backend services: identity, trips, realtime, location, dispatch, pricing, payments |
| `apps/` | Rider and driver web apps |
| `packages/` | Shared frontend packages (API client, realtime client, map) |
| `platform/` | Local infrastructure: Docker Compose, Postgres init, Traefik, OpenTelemetry, Grafana dashboards |
| `contracts/openapi/` | OpenAPI spec for each REST API |
| `contracts/events/` | JSON Schemas for Kafka events |
| `docs/adr/` | Architecture decision records |
| `docs/design/` | Design note per service |
| `docs/incidents/` | Reports for reproduced failures |
| `docs/templates/` | Templates for the documents above |
| `docs/daily/` | Daily progress log |
| `load/` | Load tests and the world simulator |
| `chaos/` | Failure-injection scripts |
| `deploy/` | Kubernetes manifests |
