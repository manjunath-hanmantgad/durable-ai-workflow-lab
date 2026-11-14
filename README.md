# Durable AI Workflow Lab

**P01 — the write/ack gap and receiver idempotency.** Part of the [Open Source AI Engineering Playbook](https://github.com/manjunath-hanmantgad/opensource-playbook).

A client sends a command to a mock ticket vendor. The vendor may commit the ticket but fail to acknowledge the response. Retries must not create duplicates. This is the smallest durable-systems proof: only the receiver's atomic unique constraint can close the gap.

## Current proof boundary

- **Proved:** same command key returns the same ticket; concurrent retries create one ticket; changed payload under the same key conflicts; the result survives receiver restart.
- **Not claimed:** real network, distributed workers, checkpoints, human approval, auth, multi-tenancy, performance, or production readiness.

## Run it

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --frozen
uv run --frozen pytest -q
```

No Docker, no database setup, no model calls, no secrets.

## Core files

- `src/p01/contracts.py` — `Command`, `Ticket`, and canonical digest.
- `src/p01/receiver.py` — SQLite mock receiver with `command_key` uniqueness.
- `tests/test_gap.py` — four pytest proofs of the gap.

## The one-sentence takeaway

A local ledger cannot prevent duplicate external writes; the external receiver must store the command key and result atomically.

## Learning focus

Explain the write/ack gap, why retries need stable keys, and why changed intent must conflict. This is interview material for FDE and AI Engineer roles, not a product demo.
