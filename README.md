# RepoClinic

RepoClinic is a deterministic repository analysis CLI built on a stateful scanner-first flow (fan-out branch analysis, fan-in roadmap synthesis). It analyzes local or GitHub repositories and produces two artifacts:

- `report.md` for human-readable engineering review
- `summary.json` for schema-validated machine consumption

## Core capabilities

- Deterministic scanner pipeline with bounded repository traversal and evidence normalization
- Parallel architecture, security, and performance analysis branches
- Checkpointed flow execution with resume support
- Structured output contracts using Pydantic models
- Optional Langfuse Cloud observability integration for run/stage traces
- Local and containerized execution paths
- Built-in quality gates via pre-commit and GitHub Actions CI

## Documentation index

- [QUICKSTART.md](QUICKSTART.md) - installation and day-one usage (local, Docker, and Makefile workflows)
- [ARCHITECTURE.md](ARCHITECTURE.md) - component design, flow execution model, and data schema
- [ROADMAP.md](ROADMAP.md) - completed milestones and forward-looking priorities
- [CONTRIBUTING.md](CONTRIBUTING.md) - contribution and review workflow
- [CHANGELOG.md](CHANGELOG.md) - release history
- [LICENSE.md](LICENSE.md) - license terms

## Minimal start

```bash
uv venv
uv sync
cp .env.example .env
uv run repoclinic validate-config
```

For runnable examples (local repo checks, GitHub checks, custom output directories, Docker runs, and Langfuse Cloud setup), use [QUICKSTART.md](QUICKSTART.md).
