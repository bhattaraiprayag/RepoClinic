# Contributing

## Contribution model

Contributions are welcome through pull requests scoped to a single objective (feature, fix, or refactor).

## Development setup

```bash
uv venv
source .venv/bin/activate
uv sync
uv run pre-commit install
```

## Engineering standards

- Follow strict TDD loops: failing test -> minimal implementation -> green tests -> refactor.
- Keep changes atomic and cohesive.
- Maintain type safety and deterministic behavior.
- Update `CHANGELOG.md` for user-visible behavior changes.

## Commit convention

Use:

`<type>(<scope>): <imperative summary>`

Supported `type` values:

- `feat`
- `fix`
- `refactor`
- `test`
- `chore`
- `docs`

## Validation before PR

```bash
make check
make precommit
make validate-config
```

GitHub Actions CI (`.github/workflows/ci.yml`) runs the same quality gates on push and pull requests.

If Docker paths were modified, also run:

```bash
make docker-build
```

## Pull request checklist

- [ ] Tests added/updated for the change
- [ ] Existing tests pass
- [ ] Changelog updated
- [ ] Documentation updated where required
