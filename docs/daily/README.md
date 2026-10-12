# Daily Log

One file per working day: what we planned, what we did, what we measured, and what we learned. Together with `docs/incidents/` and `docs/adr/`, this log is the record of how RideMesh was built.

## How to use it

1. **Start of day (5 min):** copy `_template.md` to `day-NNN-YYYY-MM-DD.md`, write the goal and the task list. Take the tasks from the plan's phase table.
2. **During the day:** tick tasks as they finish. Note problems the moment they happen, not later.
3. **End of day (10 min):** fill in *Done*, *Numbers*, *Problems and learnings*, and *Tomorrow*. Add a row to the index below.
4. Unfinished tasks move to tomorrow's plan. Never delete them silently.
5. No numbers, no done: if a task produced a measurement (memory, latency, rows, rps), it goes in *Numbers*.

File names use a three-digit day number so they sort in order: `day-001-2026-10-11.md`.

## Index

| Day | Date | Phase | Focus | Status |
| --- | --- | --- | --- | --- |
| [001](day-001-2026-10-11.md) | 2026-10-11 | 0 Foundations | Tools, repo layout, core infra in Compose, templates | Done; templates, ADR-0001 and token revoke moved to 002 |
| [002](day-002-2026-10-12.md) | 2026-10-12 | 0 Foundations | Day 1 carry-over, observability stack (traces, metrics, logs in Grafana) | In progress |
