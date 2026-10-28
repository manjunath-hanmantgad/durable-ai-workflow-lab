# Durable AI Workflow Lab

**P01 — approval-gated, crash-safe ticket creation.** Part of the [Open Source AI Engineering Playbook](https://github.com/manjunath-hanmantgad/opensource-playbook).

A fictional service request will become a validated AI draft, wait for human approval, and create a ticket through an idempotent mock API. The intended failure proof is a worker crash after the receiver commits but before local completion is recorded.

## Current proof boundary

- **Implemented and unit-tested:** strict request/draft schemas, UUID and digest boundaries, immutable validated intent, command identity, allowed state transitions, UTC/version/attempt bounds, and JSON round trips.
- **Defined, not executed:** 24 synthetic workflow scenarios in `fixtures/cases.json`.
- **Not implemented/proved:** persistent receiver deduplication, HTTP authorization, approval workflow, checkpoints, crash recovery, model quality, latency, or deployment.

A stable command key does not itself prevent duplicate actions. The planned guarantee depends on a receiver that atomically stores the key and business result. No production readiness or exactly-once execution is claimed.

## Local tests

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --frozen
uv run --frozen pytest -q
```

The current unit suite makes no network, database, or model calls. Initial dependency installation can access the package registry. PostgreSQL integration work will require a running local container runtime; there is no SQLite substitution.

## Learning focus

Learn the mechanism, break it, record evidence, and explain the trade-offs for FDE and AI Engineer interviews. Model output is untrusted data, approval is not current authorization, and a checkpoint cannot atomically commit with an independent API.

Scope is deliberately small: no frontend, multi-agent system, hosted CI/CD, real customer data, or employer-derived material. Plans, journals, credentials, and scratch remain local-only and are not required to reproduce public tests.
