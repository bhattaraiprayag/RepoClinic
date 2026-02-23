# Quickstart

This document is the canonical source for setup, execution, and troubleshooting steps.

## 1) Prerequisites

- Linux/macOS (or WSL2 on Windows)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Go](https://go.dev/doc/install) 1.25.7+ (required when installing `osv-scanner` from source)
- Docker (for container workflows)
- Git
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`)

## 2) Initial setup (without Makefile)

```bash
git clone <your-repoclinic-repo-url>
cd RepoClinic
uv venv
source .venv/bin/activate
uv sync
go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest
cp .env.example .env
```

Populate `.env` with provider credentials and optional Langfuse keys.

Verify scanner tools:

```bash
semgrep --version
bandit --version
osv-scanner --version
```

## 3) Initial setup (with Makefile)

```bash
git clone <your-repoclinic-repo-url>
cd RepoClinic
make sync
go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest
cp .env.example .env
```

## 4) Run repository checks locally (without Makefile)

CLI pattern is `uv run repoclinic <command> [options]`.
`--path`, `--repo`, and `--config` are command-specific options (not global CLI options).

### Validate configuration

```bash
uv run repoclinic validate-config --config config/settings.yaml
```

### Check a local repository

```bash
uv run repoclinic analyze \
  --path /absolute/path/to/repository \
  --output-dir artifacts/local-check
```

### Check an online GitHub repository

```bash
uv run repoclinic analyze \
  --repo https://github.com/owner/repository \
  --output-dir artifacts/remote-check
```

### Run using root `main.py`

```bash
python main.py --repo https://github.com/owner/repository
python main.py --path /absolute/path/to/repository
```

### Check a repository and store results in a specific location

```bash
uv run repoclinic analyze \
  --path /absolute/path/to/repository \
  --output-dir /absolute/path/to/output-folder
```

### Resume a previous run

```bash
uv run repoclinic resume --run-id <run-id> --output-dir artifacts/resumed
```

### Scanner scope defaults

- `tests/fixtures/**` is excluded by default from scanner profiling to prevent fixture-only technology detection in real repo reports.
- OSV scanning prefers explicit lockfiles discovered by scanner inventory, then falls back to recursive scan only when needed.

If fixture scanning is intentionally required for a custom run, use a dedicated config override that removes `tests/fixtures/**` from `scan_policy.exclude_globs`.

### LM Studio provider notes

- Use `uv run repoclinic validate-config --config config/settings.yaml` to confirm active model/profile wiring.
- Ensure `LM_STUDIO_MODEL` points to a chat-capable model ID exposed by your LM Studio `/models` endpoint.
- Validated chat-model IDs in current local compatibility checks: `qwen/qwen3-vl-30b`, `qwen3-next-80b-a3b-thinking-mlx`, and `qwen/qwen3-coder-next` (model behavior can still vary by prompt/load).
- If a specific model produces degraded branch output, rerun with a different available LM Studio model.
- Normal LM Studio usage in RepoClinic does not require running LiteLLM proxy extras.

## 5) Run repository checks locally (with Makefile)

### Check a local repository

```bash
make analyze-local REPO_PATH=/absolute/path/to/repository OUTPUT_DIR=artifacts/local-check
```

### Check an online GitHub repository

```bash
make analyze-remote REPO_URL=https://github.com/owner/repository OUTPUT_DIR=artifacts/remote-check
```

### Resume a previous run

```bash
make resume RUN_ID=<run-id> OUTPUT_DIR=artifacts/resumed
```

## 6) Run RepoClinic in Docker (without Makefile)

### Build image

```bash
docker build -t repoclinic:0.1.0 .
```

### Check a local repository

```bash
mkdir -p artifacts/docker-local
docker run --rm \
  --env-file .env \
  -v /absolute/path/to/repository:/target:ro \
  -v "$(pwd)/artifacts/docker-local:/artifacts" \
  repoclinic:0.1.0 analyze \
  --path /target \
  --output-dir /artifacts
```

### Check an online GitHub repository

```bash
mkdir -p artifacts/docker-remote
docker run --rm \
  --env-file .env \
  -v "$(pwd)/artifacts/docker-remote:/artifacts" \
  repoclinic:0.1.0 analyze \
  --repo https://github.com/owner/repository \
  --output-dir /artifacts
```

## 7) Run RepoClinic in Docker (with Makefile)

### Build image

```bash
make docker-build
```

### Check a local repository

```bash
make docker-analyze-local REPO_PATH=/absolute/path/to/repository OUTPUT_DIR=artifacts/docker-local
```

### Check an online repository

```bash
make docker-analyze-remote REPO_URL=https://github.com/owner/repository OUTPUT_DIR=artifacts/docker-remote
```

## 8) Configure Langfuse Cloud observability

RepoClinic uses these environment variables:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL` (default: `https://cloud.langfuse.com`)

### Configure credentials

```bash
cp .env.example .env
# Set the following keys from your Langfuse Cloud project settings:
# LANGFUSE_PUBLIC_KEY
# LANGFUSE_SECRET_KEY
# LANGFUSE_BASE_URL (keep https://cloud.langfuse.com unless using a regional/custom endpoint)
```

Validate that required Langfuse Cloud variables are present:

```bash
make langfuse-cloud-check
```

Then run any `analyze`/`resume` command and verify traces in Langfuse Cloud.

## 9) LM Studio troubleshooting quick checks

List available models from your configured LM Studio endpoint:

```bash
curl -sS "${LM_STUDIO_BASE_URL:-http://127.0.0.1:1234/v1}/models"
```

Run analysis with an explicit model override for isolation:

```bash
LM_STUDIO_MODEL=qwen/qwen3-vl-30b \
uv run repoclinic analyze --path /absolute/path/to/repository --provider-profile lm-studio-default
```

## 10) Quality checks and pre-commit

```bash
uv run pre-commit install
make precommit
```

## 11) Useful utility commands

```bash
make validate-config
make healthcheck
make test
make check
make precommit
```
