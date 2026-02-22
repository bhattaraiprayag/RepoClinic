# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Pre-commit integration via `.pre-commit-config.yaml` with Ruff format/lint hooks.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) for pre-commit, formatting, lint, tests, and config validation.
- New Makefile targets: `precommit` and `langfuse-cloud-check`.

### Changed
- Langfuse tracing now prioritizes `LANGFUSE_BASE_URL` for cloud-first endpoint selection.
- Runtime environment examples and tests now use `LANGFUSE_BASE_URL` instead of `LANGFUSE_HOST`.
- Makefile quality commands now use `uv run ruff` for environment-consistent lint/format behavior.
- Documentation suite updated for Langfuse Cloud-first observability and CI/pre-commit workflows.

### Fixed
- Removed unused imports that caused baseline Ruff lint failures.

### Removed
- Local self-hosted Langfuse Makefile lifecycle commands (`langfuse-up`, `langfuse-down`, `langfuse-logs`, `langfuse-env`, `langfuse-keys`).
- Legacy `.env.langfuse` workflow references across docs and ignore rules.

### Previously delivered in v0 stream
- Phase 0 baseline scaffolding with uv-managed project layout and smoke-test wiring.
- Canonical Pydantic contracts across input, scanner, branch, roadmap, summary, and flow-state payloads.
- Central YAML configuration with provider profiles, override precedence, and token budget utilities.
- Deterministic scanner pipeline with source resolution, inventory, ignore policy, heuristics, and persistence.
- Stateful scanner-first flow orchestration with checkpointed fan-out/fan-in and resume guards.
- Branch analysis execution layer (architecture/security/performance) and roadmap synthesis.
- Artifact generation for deterministic `summary.json` and fixed-section `report.md` outputs.
- CLI command surface for analyze, resume, validate-config, and healthcheck workflows.
- Observability and resilience controls, including run manifests, retry/backoff behavior, and redaction.
- Docker packaging and acceptance/e2e verification coverage.
