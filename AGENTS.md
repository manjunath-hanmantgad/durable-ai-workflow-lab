# P01 working contract (minimal)

- One bounded proof: the write/ack gap and receiver idempotency.
- Use synthetic/public inputs only; never secrets or employer artifacts.
- Write behavior tests first, observe red, then implement and run the whole suite.
- Use Python 3.12 and uv. Verification: `uv run --frozen pytest -q`.
- No Docker, PostgreSQL, FastAPI, LangGraph, telemetry, benchmarks, or cloud resources.
- Commit and push coherent feature-branch changes; never force-push or infer approval.
- Never add or force-add `docs/`, `LEARNINGS.html`, `LEARNINGS.md`, `.superpowers/`, environments, secrets, or local scratch.
- Update `LEARNINGS.html` and the parent workspace `LAB-WORKFLOW.md` at meaningful steps.
- For Archify diagrams, export the generated HTML to PNG (e.g., via Playwright) and verify images render on the public GitHub README. Do not reference the raw extracted SVG in public docs.
- For P02 onward: identify one correctness- or performance-critical component per lab and implement it in Rust. Keep Python for reference implementations, ML/AI glue, orchestration, and tests. Rust code must pass `cargo test`, `cargo clippy -- -D warnings`, include a benchmark or property/failure-injection test, and carry a short justification note explaining why Rust was chosen for that component.
- Separate proved, simulated, and unproved claims.
