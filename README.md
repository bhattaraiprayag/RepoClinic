## RepoClinic

RepoClinic is a deterministic, stateful CrewAI flow pipeline for repository analysis (ARC-FL2) that scans codebases and prepares structured inputs for architecture, security, performance, and roadmap reporting.

### Current implementation scope

This repository currently implements phases 0-5 from `planner-docs/5-IMPLEMENTATION-PLAN.md`:
- engineering baseline and governance
- canonical schema contracts
- central YAML config and model factory
- deterministic scanner/evidence pipeline
- ARC-FL2 stateful flow orchestration with checkpointed fan-out/fan-in
- branch analyzers for architecture/security/performance and roadmap trigger synthesis

### LM Studio setup note

Use `.env.example` as the variable contract for LM Studio (`LM_STUDIO_AUTH_TOKEN`, `LM_STUDIO_BASE_URL`, `LM_STUDIO_MODEL`) and select `REPOCLINIC_DEFAULT_PROVIDER_PROFILE=lm-studio-default` for local model execution.
