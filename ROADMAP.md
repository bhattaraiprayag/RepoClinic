# Roadmap

## Completed milestones

### v0 foundation (Phases 0-3)

- Project bootstrapped with uv-based workflow and contract-first schemas.
- Central config system and model factory implemented.
- Deterministic scanner pipeline and evidence persistence delivered.

### v0 orchestration and analysis (Phases 4-7)

- Stateful ARC-FL2 flow with fan-out/fan-in and resume support delivered.
- Architecture, security, and performance branch analysis integrated.
- Roadmap synthesis and artifact generation stabilized.
- CLI operator workflows completed (`analyze`, `resume`, `validate-config`, `healthcheck`).

### v0 operational hardening (Phases 8-9)

- Run manifest persistence and tracing hooks integrated.
- Retry/timeouts and redaction controls added.
- Docker packaging and acceptance-test matrix completed.

## In-progress priorities

- Consolidate local observability workflow with self-hosted Langfuse defaults.
- Expand operator ergonomics through Makefile-based execution shortcuts.
- Improve documentation quality and separation of concerns.

## Next priorities

1. Add CI workflows for automated lint/test/docker checks.
2. Improve deterministic branch heuristics for lower false-positive rates.
3. Add optional remote persistence backends for multi-run operational history.
4. Extend acceptance fixtures with larger polyglot repositories.
5. Introduce release automation and signed container publishing.
