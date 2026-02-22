# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Local self-hosted Langfuse stack assets: `docker-compose.langfuse.yml` and `.env.langfuse.example`.
- Headless Langfuse project key bootstrap path for deterministic local observability setup.
- Comprehensive `Makefile` for local runs, Docker runs, quality checks, and Langfuse lifecycle commands.
- Full documentation suite: `QUICKSTART.md`, `ARCHITECTURE.md`, `DEPLOYMENT.md`, `ROADMAP.md`, and `LICENSE.md`.

### Changed
- Runtime environment template now clarifies how Langfuse API keys are sourced in local workflows.
- Tracing integration now logs Langfuse client/emit failures without interrupting analysis runs.
- Tracing and runtime-env unit tests now use explicit typing and stricter assertions.
- Core project docs were rewritten for neutral voice, clearer structure, and lower redundancy.

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
