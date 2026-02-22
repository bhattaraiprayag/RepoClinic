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

### Changed
- LM Studio provider integration now enforces env-driven auth token usage, normalizes OpenAI-compatible base URLs, and supports env overrides for base URL/model.
- `.env.example` now includes LM Studio runtime variables and default provider profile guidance.
- Runtime dependencies now include `litellm` to support CrewAI LLM instantiation for provider-backed branch execution.
