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

## Promote a verified commit locally

From a clean checkout, run this yourself in an interactive terminal:

```sh
bash scripts/merge-local.sh
```

The command verifies the exact HEAD in a temporary detached worktree with `uv sync --frozen` and the full pytest suite. Failed, empty, skipped, or working-tree-modifying checks block promotion. It also rejects the agreed private paths anywhere in candidate history. This path guard is not a secret-content scanner; review the diff before approving.

After verification it asks you to type `merge <full verified SHA>`. Only then does it recheck remote state and make a normal fast-forward push to `origin/main`. It refuses a moved/diverged main and never force-pushes or bypasses repository protections. If main does not exist, the distinct confirmation is `create main <full verified SHA>`. It does not check out/reset your local main branch.

No automatic approval flag or piped confirmation is supported. Agents must not supply the owner's approval. The tool's tests exercise approval only in disposable local repositories; they never promote this repository on GitHub.

Logs remain under ignored `.superpowers/merges/<SHA>/`. No GitHub Actions, hosted CI/CD, model calls, or cloud deployment are added. Local dependency setup may contact the package registry; later required integration tests will need their local runtime and must not be skipped to get a green merge.

The method assumes a trusted local Git/toolchain and reviewed test code. Normal Git fast-forward protection handles divergent races; this is not a branch-protection replacement or a cryptographically signed approval service.

## Learning focus

Learn the mechanism, break it, record evidence, and explain the trade-offs for FDE and AI Engineer interviews. Model output is untrusted data, approval is not current authorization, and a checkpoint cannot atomically commit with an independent API.

Scope is deliberately small: no frontend, multi-agent system, hosted CI/CD, real customer data, or employer-derived material. Plans, journals, credentials, and scratch remain local-only and are not required to reproduce public tests.
