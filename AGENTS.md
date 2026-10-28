# P01 working contract

- Own one bounded workflow proof. Do not implement neighboring playbook labs or a product UI.
- Use synthetic/public/shareable inputs only; never secrets or employer artifacts.
- State each step's outcome, done checks, learning goal, verification, and exclusions.
- Write behavior tests first, observe red, then implement and run the whole suite.
- Use Python 3.12 and the uv lockfile. Current verification: `uv run --frozen pytest -q`.
- No GitHub Actions, hosted CI/CD, paid model calls, or cloud resources without explicit authorization.
- Commit and push coherent feature-branch changes; never force-push or infer approval to promote main.
- Never add or force-add `docs/`, `LEARNINGS.html`, `LEARNINGS.md`, `.superpowers/`, environments, secrets, or local scratch. Inspect staged files before commits and committed files before pushes.
- If local `LEARNINGS.html` or the parent workspace `LAB-WORKFLOW.md` exists, read and update it at meaningful steps. Public setup/tests must work without these private files.
- Capture authentic evidence-backed blog/LinkedIn/X drafts incrementally, locally. No personal learning claims, invented metrics, or social publication without owner review.
- Separate proved, simulated, and unproved claims. Unit validation is not authorization, durability, receiver deduplication, model quality, or production readiness.
