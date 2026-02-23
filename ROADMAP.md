# Roadmap

## Completed milestones

### v0 foundation (Phases 0-3)

- Project bootstrapped with uv-based workflow and contract-first schemas.
- Central config system and model factory implemented.
- Deterministic scanner pipeline and evidence persistence delivered.

### v0 orchestration and analysis (Phases 4-7)

- Stateful scanner-first flow with fan-out/fan-in and resume support delivered.
- Architecture, security, and performance branch analysis integrated.
- Roadmap synthesis and artifact generation stabilized.
- CLI operator workflows completed (`analyze`, `resume`, `validate-config`, `healthcheck`).

### v0 operational hardening (Phases 8-9)

- Run manifest persistence and tracing hooks integrated.
- Retry/timeouts and redaction controls added.
- Docker packaging and acceptance-test matrix completed.
- Langfuse observability workflow migrated to Langfuse Cloud (`LANGFUSE_BASE_URL`).

### v0 developer workflow hardening

- Pre-commit checks integrated for formatter/lint enforcement.
- GitHub Actions CI workflow added for pre-commit, formatting, lint, tests, and config validation.
- Makefile quality/observability targets updated for cloud-first operations.
- Scanner scope hardening delivered (`tests/fixtures/**` excluded by default) to reduce false-positive tech detection.
- LM Studio branch execution hardening delivered for noisy LiteLLM proxy-import logging and schema-variance normalization.

## In-progress priorities

- Expand provider/model compatibility matrix testing for LM Studio model behavior consistency.
- Improve deterministic branch heuristics for lower non-actionable finding rates.
- Add optional remote persistence backends for multi-run operational history.
- Extend acceptance fixtures with larger polyglot repositories.

## Next priorities

1. Introduce release automation and signed container publishing.
2. Add matrix CI coverage for multiple Python/runtime environments.
3. Add observability dashboards and SLO alerts for long-running analyses.
4. Expand Docker image hardening (SBOM + vulnerability gating).
