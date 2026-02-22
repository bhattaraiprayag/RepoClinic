# Contributing

## Workflow

1. Follow strict TDD loops for every atomic task:
   - write a failing test
   - implement minimal code
   - make tests pass
   - refactor safely when needed
2. Keep changes scoped to one atomic task per commit.
3. Update `CHANGELOG.md` before each commit.

## Commit convention

Use:

`<type>(<scope>): <imperative summary>`

Allowed types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`.

## Local development

- Use `uv` for dependency and environment management.
- Run tests with `uv run pytest`.
