# Quickstart

## 1) Prerequisites

- Linux/macOS (or WSL2 on Windows)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for container workflows)
- Git

## 2) Initial setup (without Makefile)

```bash
git clone <your-repoclinic-repo-url>
cd RepoClinic
uv venv
source .venv/bin/activate
uv sync
cp .env.example .env
```

Populate `.env` with provider credentials and optional Langfuse keys.

## 3) Initial setup (with Makefile)

```bash
git clone <your-repoclinic-repo-url>
cd RepoClinic
make sync
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

## 9) Quality checks and pre-commit

```bash
uv run pre-commit install
make precommit
```

## 10) Useful utility commands

```bash
make validate-config
make healthcheck
make test
make check
make precommit
```
