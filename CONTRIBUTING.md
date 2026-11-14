# Contributing

Thanks for your interest in Durable Command Receiver.

This is a small, focused reference implementation. The goal is to keep the core contract clear and well-tested. Contributions that add scope (HTTP, auth, multi-tenancy, orchestration) are better suited to a fork or a downstream project.

## Ways to contribute

- Report bugs or unclear explanations by opening an issue.
- Simplify code or tests without changing behavior.
- Improve diagrams or documentation.
- Add a failing test that exposes a real gap in the contract.

## Development setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --frozen
uv run --frozen pytest -q
```

## Pull request guidelines

- Keep the change small and focused.
- Include or update tests for any behavior change.
- Update the README if the public interface changes.
- Do not add new dependencies unless absolutely necessary.

## Code of conduct

Be respectful and assume good intent.
