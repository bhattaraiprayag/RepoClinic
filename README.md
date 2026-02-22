# RepoClinic

RepoClinic is a scanner-first repository analysis CLI built with CrewAI flow orchestration. It analyzes a GitHub URL or local folder and generates:

- `report.md` (human-readable engineering report)
- `summary.json` (structured machine-readable summary)

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Git
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`)
- [Go](https://go.dev/doc/install) 1.25.7+ (required when installing `osv-scanner` from source)
- Docker (optional, for containerized runs)

### Install and bootstrap

```bash
uv venv
source .venv/bin/activate
uv sync
go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest
cp .env.example .env
```

Verify scanner tooling is present:

```bash
semgrep --version
bandit --version
osv-scanner --version
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
