# Contributing

## Contribution model

Contributions are welcome through pull requests scoped to a single objective (feature, fix, or refactor).

## Development setup

```bash
uv venv
source .venv/bin/activate
uv sync
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
make validate-config
```

If Docker paths were modified, also run:

```bash
make docker-build
```

## Pull request checklist

- [ ] Tests added/updated for the change
- [ ] Existing tests pass
- [ ] Changelog updated
- [ ] Documentation updated where required
