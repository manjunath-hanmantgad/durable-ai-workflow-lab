# P01 working contract (minimal)

- One bounded proof: the write/ack gap and receiver idempotency.
- Use synthetic/public inputs only; never secrets or employer artifacts.
- Write behavior tests first, observe red, then implement and run the whole suite.
- Use Python 3.12 and uv. Verification: `uv run --frozen pytest -q`.
- No Docker, PostgreSQL, FastAPI, LangGraph, telemetry, benchmarks, or cloud resources.
- Commit and push coherent feature-branch changes; never force-push or infer approval.
- Never add or force-add `docs/`, `LEARNINGS.html`, `LEARNINGS.md`, `.superpowers/`, environments, secrets, or local scratch.
- Update `LEARNINGS.html` and the parent workspace `LAB-WORKFLOW.md` at meaningful steps.
- Separate proved, simulated, and unproved claims.
