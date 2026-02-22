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

.PHONY: \
	help venv sync clean \
	format lint test check precommit \
	validate-config analyze-local analyze-remote resume healthcheck \
	docker-build docker-analyze-local docker-analyze-remote docker-healthcheck \
	langfuse-cloud-check

help:
	@echo "RepoClinic developer targets"
	@echo "  venv                  Create .venv via uv"
	@echo "  sync                  Install/update dependencies"
	@echo "  format                Format src/tests with ruff"
	@echo "  lint                  Lint src/tests with ruff"
	@echo "  test                  Run pytest"
	@echo "  check                 Run lint + tests"
	@echo "  precommit             Run pre-commit checks on all files"
	@echo "  validate-config       Validate config/settings.yaml"
	@echo "  analyze-local         Analyze local repo (REPO_PATH required)"
	@echo "  analyze-remote        Analyze GitHub repo URL (REPO_URL required)"
	@echo "  resume                Resume run (RUN_ID required)"
	@echo "  healthcheck           Run RepoClinic healthcheck"
	@echo "  docker-build          Build RepoClinic Docker image"
	@echo "  docker-analyze-local  Analyze local repo via Docker (REPO_PATH required)"
	@echo "  docker-analyze-remote Analyze GitHub repo via Docker (REPO_URL required)"
	@echo "  docker-healthcheck    Run healthcheck inside Docker image"
	@echo "  langfuse-cloud-check  Verify required Langfuse Cloud vars exist in .env"

venv:
	$(UV) venv

sync: venv
	$(UV) sync

format:
	$(UV) run ruff format src tests

lint:
	$(UV) run ruff check src tests

test:
	$(UV) run pytest

check: lint test

precommit:
	$(UV) run pre-commit run --all-files

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

langfuse-cloud-check:
	@if [ ! -f ".env" ]; then echo ".env not found. Copy .env.example to .env first."; exit 1; fi
	@grep -q '^LANGFUSE_PUBLIC_KEY=' .env || (echo "Missing LANGFUSE_PUBLIC_KEY in .env"; exit 1)
	@grep -q '^LANGFUSE_SECRET_KEY=' .env || (echo "Missing LANGFUSE_SECRET_KEY in .env"; exit 1)
	@grep -q '^LANGFUSE_BASE_URL=' .env || (echo "Missing LANGFUSE_BASE_URL in .env"; exit 1)
	@echo "Langfuse Cloud variables detected in .env"

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
