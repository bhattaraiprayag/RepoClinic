# Quickstart

## 1) Prerequisites

- Linux/macOS (or WSL2 on Windows)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose (for container workflows and local Langfuse)
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

## 8) Run local Langfuse for observability

RepoClinic uses these environment variables:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` (for local setup use `http://localhost:3000`)

### Start Langfuse stack (without Makefile)

```bash
cp .env.langfuse.example .env.langfuse
# Update all placeholder secrets before starting

docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml up -d
```

### Start Langfuse stack (with Makefile)

```bash
make langfuse-up
```

### Where to get Langfuse public/secret keys

Use either approach:

1. **UI-based keys** (default Langfuse behavior): open Langfuse at `http://localhost:3000`, create organization/project, then read keys in **Project Settings -> API Keys**.
2. **Headless initialization keys**: set `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` and `LANGFUSE_INIT_PROJECT_SECRET_KEY` in `.env.langfuse`; these become the project keys on startup.

After choosing one approach, copy the resulting values into RepoClinic `.env`:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

Then run any `analyze`/`resume` command and verify traces in Langfuse.

### Stop Langfuse

```bash
make langfuse-down
# or
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml down
```

## 9) Useful utility commands

```bash
make validate-config
make healthcheck
make test
make check
```
