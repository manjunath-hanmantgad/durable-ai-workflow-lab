# Durable AI Workflow Lab — P01

> **The write/ack gap:** why retries need an idempotent receiver, not just a brave client.

Part of the [Open Source AI Engineering Playbook](https://github.com/manjunath-hanmantgad/opensource-playbook).

## The problem in one scenario

```text
client -> receiver: create ticket (key = "req-1")
receiver -> database: INSERT ticket
receiver -> client: [response lost]
client -> receiver: create ticket (key = "req-1")  -- retry
```

Without receiver-side idempotency, the retry creates a second ticket. With it, the receiver returns the **same ticket** it already committed.

This repository is a minimal, runnable proof of that idea.

## What is proved here

- A retry with the same `command_key` returns the original `ticket_id`.
- Ten concurrent retries still create exactly one ticket.
- Reusing a key with a changed payload is rejected as a conflict.
- The stored result survives a receiver restart.

```text
uv sync --frozen
uv run --frozen pytest -q
```

No Docker, no database setup, no model calls, no secrets. Runs in ~0.05 s.

## The core idea

A local ledger or workflow checkpoint cannot prevent duplicate external writes. Only the external receiver can, by atomically storing:

1. the stable command key, and
2. the business result it produced.

If the key already exists with the same payload, return the stored result. If the key exists with a different payload, conflict. That is the smallest durable-systems guarantee.

## File map

| File | Responsibility |
| --- | --- |
| `src/p01/contracts.py` | `Command`, `Ticket`, and a canonical SHA-256 digest. |
| `src/p01/receiver.py` | SQLite-backed mock receiver with `UNIQUE(command_key)`. |
| `tests/test_gap.py` | Five pytest proofs of retry, concurrency, conflict, and restart survival. |

## What this is *not*

- Not a production workflow engine.
- No HTTP API, auth, multi-tenancy, LangGraph, PostgreSQL, checkpoints, or distributed workers.
- No real network, model, or ticket vendor.
- No performance or scale claims.

It is one interview-ready concept made concrete.

## Interview takeaway

> **Why can't a client just check its own log before retrying?**
>
> The write and the acknowledgement are separate events. The receiver may commit a ticket and then crash, drop the response, or lose the network before the client learns the outcome. The client's log can never know for sure whether the write happened. Only the receiver's atomic store of `(command_key, result)` can answer that question on retry.

## Learning goal

Explain the write/ack gap, why retries need stable keys, and why changed intent must conflict — in your own words, without the code in front of you.

## License

MIT — see `LICENSE` if included, otherwise the playbook repository governs usage.
