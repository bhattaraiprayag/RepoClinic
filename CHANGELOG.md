# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 0 baseline scaffolding with uv-managed project layout.
- CLI entrypoint wiring and smoke tests.
- Baseline contributor workflow and governance documentation.
- Canonical Pydantic schema contracts for input, scanner, middle-branch, roadmap, summary, and ARC-FL2 flow state payloads.
- Central YAML configuration system with validated provider profiles, override precedence, token budgeting utility, and CrewAI model factory.
- Deterministic scanner pipeline with source resolution, rg-based inventory, ignore policy, framework/entrypoint heuristics, tool runner normalization hooks, and SQLite scanner checkpoint persistence.
- Unit and integration tests for contracts, config/model factory behavior, inventory edge cases, and scanner output persistence.
- ARC-FL2 flow orchestration with scanner-first execution, checkpointed fan-out/fan-in branch execution, transition logging, and resume/idempotency guards.
- Phase 5 branch executor layer including deterministic analyzers, CrewAI-backed branch executor, failed-branch payload builders, and roadmap synthesis helper.
- Integration tests for flow ordering, partial-failure behavior, transition logging, and resume semantics.
- Branch analyzer tests validating evidence-linked findings and roadmap synthesis contracts.
- Phase 6 artifact generation layer with validated `summary.json` assembly, deterministic risk/roadmap ordering, fixed-section `report.md` rendering, and output writers.
- Phase 7 CLI workflow with `analyze`, `resume`, and `validate-config` commands, rich status panels, provider profile selection, output directory controls, and hard-failure exit behavior.
- Unit/integration test coverage for artifact schema/report contracts and CLI workflows (argument validation, resume path, config validation, artifact emission).
- Phase 8 observability and resilience controls: retry/backoff/jitter execution helper, run manifest capture/persistence, Langfuse tracer integration hooks, and sensitive log redaction utilities.
- Phase 9 packaging assets: Dockerfile with pinned toolchain versions and runtime healthcheck, plus acceptance matrix e2e tests (small/multi-language, large-file handling, partial-failure, deterministic rerun).

### Changed
- LM Studio provider integration now enforces env-driven auth token usage, normalizes OpenAI-compatible base URLs, and supports env overrides for base URL/model.
- LM Studio config/model normalization now standardizes `lm_studio/` model prefixes, accepts `LM_STUDIO_API_BASE`, and supports `LM_STUDIO_API_KEY` as a compatibility alias.
- `.env.example` now includes LM Studio runtime variables and default provider profile guidance.
- Runtime dependencies now include `litellm` to support CrewAI LLM instantiation for provider-backed branch execution.
- Flow runner now exposes artifact materialization from persisted ARC-FL2 state to support post-flow report generation and resume workflows.
- CLI now supports branch executor mode selection (`crewai` or `heuristic`) and redacts sensitive error values in output paths.
- Flow orchestration now applies retry policies/timeouts at scanner and branch stages, redacts failure reasons, and persists per-run metadata manifests.
