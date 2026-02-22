# Architecture

## 1) System overview

RepoClinic implements a scanner-first stateful flow as a deterministic pipeline:

```mermaid
flowchart TD
    CLI["Typer CLI<br>(analyze/resume/validate-config)"] --> FlowRunner[RepoClinicFlowRunner]
    FlowRunner --> Start[Validate request + state]
    Start --> Scanner[Deterministic scanner stage]
    Scanner --> Arch[Architecture branch]
    Scanner --> Sec[Security branch]
    Scanner --> Perf[Performance branch]
    Arch --> Join[Roadmap synthesis join]
    Sec --> Join
    Perf --> Join
    Join --> Artifacts[summary.json + report.md]

    FlowRunner --> Manifest["Run manifest store<br>SQLite"]
    Start --> TransitionLog["Flow transition log<br>SQLite"]
    Scanner --> ScannerStore["Scanner persistence<br>SQLite"]
    FlowRunner --> Tracing["Langfuse tracer<br>optional"]
```

## 2) Component boundaries

| Component | Responsibility |
|---|---|
| `repoclinic.cli` | Operator-facing commands and input validation |
| `repoclinic.flow` | Flow orchestration, checkpointing, resume logic |
| `repoclinic.scanner` | Deterministic source resolution, inventory, heuristics, evidence normalization |
| `repoclinic.agents` | Branch analyzers and roadmap synthesis |
| `repoclinic.artifacts` | Deterministic `summary.json` and `report.md` generation |
| `repoclinic.config` | Typed config loading and provider profile resolution |
| `repoclinic.observability` | Run manifest persistence and optional Langfuse tracing |

## 3) Flow execution model

1. Validate request payload and provider profile.
2. Execute scanner stage first (deterministic, bounded by scan policy and timeouts).
3. Fan out architecture/security/performance branches.
4. Fan in to roadmap synthesis after branch completion (including degraded outcomes).
5. Materialize report artifacts and persist metadata.

## 4) Data schema (SQLite)

RepoClinic persists scanner snapshots, transition logs, and run manifests in SQLite.

```mermaid
erDiagram
    RUNS ||--|| SCANNER_OUTPUTS : stores
    RUNS ||--o{ FLOW_TRANSITIONS : records
    RUNS ||--|| RUN_MANIFESTS : captures

    RUNS {
      text run_id PK
      text schema_version
      text repo_name
      text resolved_path
      text status
      text started_at
      text finished_at
    }

    SCANNER_OUTPUTS {
      text run_id PK
      text payload_json
    }

    FLOW_TRANSITIONS {
      text run_id
      text node_id
      text from_state
      text to_state
      text timestamp
      text reason
    }

    RUN_MANIFESTS {
      text run_id PK
      text created_at
      text payload_json
    }
```

## 5) External interfaces

- **Input surfaces**
  - local path (`--path`)
  - GitHub URL (`--repo`)
- **Output surfaces**
  - `summary.json`
  - `report.md`
- **Observability surface**
  - Langfuse SDK over `LANGFUSE_HOST`
- **Toolchain dependencies**
  - `git`, `rg`, `semgrep`, `bandit`, `osv-scanner`

## 6) Runtime control points

- Provider switching is config-driven (`config/settings.yaml` + env overrides).
- Retry/timeout behavior is centrally configured and applied by flow stages.
- Branch execution can run through CrewAI-backed models or deterministic heuristic mode.
