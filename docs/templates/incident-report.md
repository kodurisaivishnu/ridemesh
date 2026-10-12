<!--
Copy to docs/incidents/NN-<slug>.md (two digits, next free number). One page.
Write it the day the problem is fixed, while the numbers and graphs are fresh.
-->

# Incident NN: Short description of what users saw

- **Date:** YYYY-MM-DD
- **Plan problem:** backend N | data N | frontend N, or "found by accident"
- **Services involved:**
- **Severity:** what share of requests or trips were affected, and for how long

## Symptom

What users or the dashboard showed, in numbers: error rate, p99, stuck trips, double charges.

## How it was reproduced

The load (tool, rps, number of drivers and riders) and the failure injected (`make chaos-…`, a config change). Someone else should be able to repeat it from this section alone.

## How it was detected

The alert, panel, trace or log line that showed it first. If nothing caught it, say so: that is a finding too.

## Root cause

The mechanism, not the trigger. Ask "why" until the answer is something in the design.

## Fix

What changed, with links to the commits. The pattern used (outbox, retry budget, idempotency key, …).

## Before and after

| Metric | Before | After |
| --- | --- | --- |
| | | |

Grafana panel: screenshot or link, with the same time range and load for both runs.

## Prevention

What stops this from coming back: a test, an alert, a CI check, a chaos script in `chaos/`.

## What I learned

One or two sentences.

## Resume line

One bullet: action, the number it moved, and the scale. Example: "Cut duplicate charges from 1.8% to 0 at 300 rps by adding idempotency keys and an inbox table to the Payments consumer."
