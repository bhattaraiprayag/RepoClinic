# RepoClinic

RepoClinic is a scanner-first repository analysis CLI built with CrewAI flow orchestration. It analyzes a GitHub URL or local folder and generates:

- `report.md` (human-readable engineering report)
- `summary.json` (structured machine-readable summary)

## Setup

Use [QUICKSTART.md](QUICKSTART.md) for canonical setup, tool installation, Docker usage, and troubleshooting guidance.

If the environment is already prepared:

```bash
uv sync
cp .env.example .env
```

## How to run

### Preferred CLI

```bash
uv run repoclinic analyze --repo https://github.com/owner/repo --output-dir artifacts
uv run repoclinic analyze --path /absolute/path/to/repo --output-dir artifacts
```

### Requirement-compatible root entrypoint

```bash
python main.py --repo https://github.com/owner/repo
python main.py --path /absolute/path/to/repo
```

## Agent design choices

RepoClinic follows a scanner-first dependency chain:

1. **Code Scanner stage** (deterministic tooling and filesystem analysis)
2. **Architecture Analyst Agent**
3. **Security Agent**
4. **Performance Agent**
5. **Roadmap Planner Agent** (CrewAI-first with deterministic fallback)

The scanner stage executes first, architecture/security/performance depend on scanner output, and roadmap synthesis runs after all three complete.

## Reliability updates in current release

- Scanner scope now excludes `tests/fixtures/**` by default to avoid fixture-driven repo-profile false positives.
- Dependency vulnerability scanning now prioritizes explicit lockfile targets before recursive fallback scanning.
- LM Studio provider setup now guards LiteLLM cold-storage proxy imports to avoid noisy non-fatal `fastapi` dependency logs.
- Crew branch outputs are normalized before schema validation to improve resilience across LM Studio model output variance.

## Known limitations

- Findings are static-analysis and heuristic-driven; runtime behavior is inferred, not executed.
- Detection quality depends on scanner availability (`semgrep`, `bandit`, `osv-scanner`) and repository signal quality.
- Extremely large repositories may require tighter scan-policy tuning for execution time.

## Scaling approach

- Keep scanner execution deterministic with bounded file traversal and configurable limits.
- Run branch analysis in parallel to minimize end-to-end latency.
- Use checkpointed flow persistence for resumability and fault tolerance.
- Containerize execution for reproducible scanner/toolchain versions in CI/CD.

## Documentation index

- [QUICKSTART.md](QUICKSTART.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ROADMAP.md](ROADMAP.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CHANGELOG.md](CHANGELOG.md)
- [LICENSE.md](LICENSE.md)
