SHELL := /bin/bash
.DEFAULT_GOAL := help

UV ?= uv
DOCKER_IMAGE ?= repoclinic:0.1.0
OUTPUT_DIR ?= artifacts
DB_PATH ?= .sqlite/repoclinic.db
WORKSPACE_ROOT ?= .scanner-workspace
CONFIG ?= config/settings.yaml
BRANCH_EXECUTOR ?= heuristic
REPO_PATH ?=
REPO_URL ?=
RUN_ID ?=
LANGFUSE_COMPOSE_FILE ?= docker-compose.langfuse.yml
LANGFUSE_ENV_FILE ?= .env.langfuse

.PHONY: \
	help venv sync clean \
	format lint test check \
	validate-config analyze-local analyze-remote resume healthcheck \
	docker-build docker-analyze-local docker-analyze-remote docker-healthcheck \
	langfuse-env langfuse-up langfuse-logs langfuse-down langfuse-keys

help:
	@echo "RepoClinic developer targets"
	@echo "  venv                  Create .venv via uv"
	@echo "  sync                  Install/update dependencies"
	@echo "  format                Format src/tests with ruff"
	@echo "  lint                  Lint src/tests with ruff"
	@echo "  test                  Run pytest"
	@echo "  check                 Run lint + tests"
	@echo "  validate-config       Validate config/settings.yaml"
	@echo "  analyze-local         Analyze local repo (REPO_PATH required)"
	@echo "  analyze-remote        Analyze GitHub repo URL (REPO_URL required)"
	@echo "  resume                Resume run (RUN_ID required)"
	@echo "  healthcheck           Run RepoClinic healthcheck"
	@echo "  docker-build          Build RepoClinic Docker image"
	@echo "  docker-analyze-local  Analyze local repo via Docker (REPO_PATH required)"
	@echo "  docker-analyze-remote Analyze GitHub repo via Docker (REPO_URL required)"
	@echo "  docker-healthcheck    Run healthcheck inside Docker image"
	@echo "  langfuse-env          Create .env.langfuse from template if missing"
	@echo "  langfuse-up           Start local Langfuse stack"
	@echo "  langfuse-logs         Tail Langfuse logs"
	@echo "  langfuse-down         Stop local Langfuse stack"
	@echo "  langfuse-keys         Show headless init keys from .env.langfuse"

venv:
	$(UV) venv

sync: venv
	$(UV) sync

format:
	uvx ruff format src tests

lint:
	uvx ruff check src tests

test:
	$(UV) run pytest

check: lint test

validate-config:
	$(UV) run repoclinic validate-config --config "$(CONFIG)"

analyze-local:
	@if [ -z "$(REPO_PATH)" ]; then echo "Set REPO_PATH=/absolute/path/to/repo"; exit 1; fi
	$(UV) run repoclinic analyze --path "$(REPO_PATH)" --output-dir "$(OUTPUT_DIR)" --db-path "$(DB_PATH)" --workspace-root "$(WORKSPACE_ROOT)" --config "$(CONFIG)" --branch-executor "$(BRANCH_EXECUTOR)"

analyze-remote:
	@if [ -z "$(REPO_URL)" ]; then echo "Set REPO_URL=https://github.com/owner/repo"; exit 1; fi
	$(UV) run repoclinic analyze --repo "$(REPO_URL)" --output-dir "$(OUTPUT_DIR)" --db-path "$(DB_PATH)" --workspace-root "$(WORKSPACE_ROOT)" --config "$(CONFIG)" --branch-executor "$(BRANCH_EXECUTOR)"

resume:
	@if [ -z "$(RUN_ID)" ]; then echo "Set RUN_ID=<existing-run-id>"; exit 1; fi
	$(UV) run repoclinic resume --run-id "$(RUN_ID)" --output-dir "$(OUTPUT_DIR)" --db-path "$(DB_PATH)" --workspace-root "$(WORKSPACE_ROOT)" --config "$(CONFIG)" --branch-executor "$(BRANCH_EXECUTOR)"

healthcheck:
	$(UV) run repoclinic healthcheck --config "$(CONFIG)" --db-path "$(DB_PATH)"

docker-build:
	docker build -t "$(DOCKER_IMAGE)" .

docker-analyze-local:
	@if [ -z "$(REPO_PATH)" ]; then echo "Set REPO_PATH=/absolute/path/to/repo"; exit 1; fi
	@mkdir -p "$(OUTPUT_DIR)"
	docker run --rm --env-file .env -v "$(REPO_PATH):/target:ro" -v "$(PWD)/$(OUTPUT_DIR):/artifacts" "$(DOCKER_IMAGE)" analyze --path /target --output-dir /artifacts --db-path /artifacts/repoclinic.db --workspace-root /tmp/repoclinic-workspace --branch-executor "$(BRANCH_EXECUTOR)"

docker-analyze-remote:
	@if [ -z "$(REPO_URL)" ]; then echo "Set REPO_URL=https://github.com/owner/repo"; exit 1; fi
	@mkdir -p "$(OUTPUT_DIR)"
	docker run --rm --env-file .env -v "$(PWD)/$(OUTPUT_DIR):/artifacts" "$(DOCKER_IMAGE)" analyze --repo "$(REPO_URL)" --output-dir /artifacts --db-path /artifacts/repoclinic.db --workspace-root /tmp/repoclinic-workspace --branch-executor "$(BRANCH_EXECUTOR)"

docker-healthcheck:
	docker run --rm --env-file .env "$(DOCKER_IMAGE)" healthcheck --quiet

langfuse-env:
	@if [ ! -f "$(LANGFUSE_ENV_FILE)" ]; then cp .env.langfuse.example "$(LANGFUSE_ENV_FILE)"; echo "Created $(LANGFUSE_ENV_FILE). Update secrets before use."; fi

langfuse-up: langfuse-env
	docker compose --env-file "$(LANGFUSE_ENV_FILE)" -f "$(LANGFUSE_COMPOSE_FILE)" up -d

langfuse-logs:
	docker compose --env-file "$(LANGFUSE_ENV_FILE)" -f "$(LANGFUSE_COMPOSE_FILE)" logs -f --tail=200

langfuse-down:
	docker compose --env-file "$(LANGFUSE_ENV_FILE)" -f "$(LANGFUSE_COMPOSE_FILE)" down

langfuse-keys: langfuse-env
	@grep -E '^LANGFUSE_INIT_PROJECT_(PUBLIC|SECRET)_KEY=' "$(LANGFUSE_ENV_FILE)" || true

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
