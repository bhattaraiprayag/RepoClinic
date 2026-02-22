## RepoClinic

RepoClinic is a deterministic, stateful ARC-FL2 CrewAI flow for repository analysis that outputs:
- `report.md` (human-readable engineering report)
- `summary.json` (schema-validated machine output)

## Setup

1. Install dependencies with `uv`:
   - `uv sync`
2. Copy environment template:
   - `cp .env.example .env`
3. Populate `.env` with provider credentials (OpenAI and/or LM Studio, optional Langfuse).

## Run

Validate config:
- `python -m repoclinic validate-config`

Analyze a local repository:
- `python -m repoclinic analyze --path /absolute/path/to/repo --output-dir artifacts`

Analyze a GitHub repository:
- `python -m repoclinic analyze --repo https://github.com/user/repo --output-dir artifacts`

Resume a run:
- `python -m repoclinic resume --run-id <run_id> --output-dir artifacts`

Healthcheck:
- `python -m repoclinic healthcheck`

Docker build/run:
- `docker build -t repoclinic:0.1.0 .`
- `docker run --rm -v /absolute/repo:/target repoclinic:0.1.0 analyze --path /target --output-dir /target/.repoclinic-artifacts --branch-executor heuristic`

## Architecture rationale

The implementation follows ARC-FL2 from `planner-docs/5-IMPLEMENTATION-PLAN.md`:
1. Start + validation
2. Deterministic scanner stage
3. Fan-out branches (architecture/security/performance)
4. Fan-in roadmap trigger
5. Artifact materialization

Flow state is checkpointed in SQLite, transitions are logged, retries/backoff/jitter are applied at scanner/branch stages, and run manifests capture reproducibility metadata.

## Known limitations

- CrewAI branch execution requires provider credentials; use `--branch-executor heuristic` for deterministic offline operation.
- Security/performance depth depends on deterministic scanner evidence and enabled external tools.
- Dockerfile pins tool versions and expects compatible package repositories for those exact pins.

## Scale path

- Add distributed job partitioning only when throughput data justifies moving beyond single-node ARC-FL2.
- Expand language-specific evidence extraction and suppression registries to reduce false positives.
- Add richer observability correlation (trace IDs in artifacts, latency SLO dashboards) and CI acceptance gates.
