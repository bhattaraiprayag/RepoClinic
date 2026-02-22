"""Run metadata capture and persistence for phase 8."""

from __future__ import annotations

import platform
import re
import sqlite3
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import orjson
from pydantic import Field

from repoclinic.config.models import AppConfig
from repoclinic.constants import PROMPT_VERSIONS
from repoclinic.schemas.base import StrictSchemaModel
from repoclinic.schemas.input_models import (
    AnalyzeRequest,
    PromptVersions,
    RepoMetadata,
    ToolVersions,
)
from repoclinic.security.redaction import redact_mapping

GITHUB_REPO_PATTERN = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)")


class ProviderManifest(StrictSchemaModel):
    """Provider execution metadata."""

    profile: str
    provider_type: str
    model: str


class RetryManifest(StrictSchemaModel):
    """Retry profile metadata."""

    max_attempts: int
    backoff_seconds: float
    jitter_seconds: float


class TimeoutManifest(StrictSchemaModel):
    """Timeout profile metadata."""

    scanner_seconds: int
    agent_seconds: int


class RunManifest(StrictSchemaModel):
    """Full run manifest for reproducibility and observability."""

    schema_version: str
    run_id: str
    created_at: str
    repo: RepoMetadata
    provider: ProviderManifest
    tool_versions: ToolVersions
    prompt_versions: PromptVersions
    retries: RetryManifest
    timeouts: TimeoutManifest
    analysis_status: dict[str, str] = Field(default_factory=dict)
    branch_failures: dict[str, str] = Field(default_factory=dict)


class RunManifestCollector:
    """Collects reproducibility metadata for each run."""

    def __init__(self, *, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def collect(
        self,
        *,
        request: AnalyzeRequest,
        config: AppConfig,
        provider_profile: str,
        branch_statuses: dict[str, str],
        branch_failures: dict[str, str],
    ) -> RunManifest:
        profile = config.provider_profiles[provider_profile]
        repo_name, resolved_path = self._resolve_repo_location(
            request=request,
            run_id=request.run_id,
        )
        repo_metadata = RepoMetadata(
            repo_name=repo_name,
            resolved_path=str(resolved_path),
            git_commit_sha=self._resolve_git_sha(resolved_path),
        )
        return RunManifest(
            schema_version=request.schema_version,
            run_id=request.run_id,
            created_at=datetime.now(UTC).isoformat(),
            repo=repo_metadata,
            provider=ProviderManifest(
                profile=provider_profile,
                provider_type=profile.provider_type.value,
                model=profile.model,
            ),
            tool_versions=ToolVersions(
                crewai=self._package_version("crewai"),
                python=platform.python_version(),
                semgrep=self._tool_version(["semgrep", "--version"]),
                bandit=self._tool_version(["bandit", "--version"]),
                osv_scanner=self._tool_version(["osv-scanner", "--version"]),
                ripgrep=self._tool_version(["rg", "--version"]),
            ),
            prompt_versions=PromptVersions(
                scanner=PROMPT_VERSIONS["scanner"],
                architecture=PROMPT_VERSIONS["architecture"],
                security=PROMPT_VERSIONS["security"],
                performance=PROMPT_VERSIONS["performance"],
                roadmap=PROMPT_VERSIONS["roadmap"],
            ),
            retries=RetryManifest(
                max_attempts=config.retries.max_attempts,
                backoff_seconds=config.retries.backoff_seconds,
                jitter_seconds=config.retries.jitter_seconds,
            ),
            timeouts=TimeoutManifest(
                scanner_seconds=config.timeouts.scanner_seconds,
                agent_seconds=config.timeouts.agent_seconds,
            ),
            analysis_status=dict(branch_statuses),
            branch_failures=redact_mapping(dict(branch_failures)),
        )

    def _resolve_repo_location(self, *, request: AnalyzeRequest, run_id: str) -> tuple[str, Path]:
        if request.input.source_type == "local_path":
            assert request.input.local_path is not None
            path = Path(request.input.local_path).expanduser().resolve()
            return path.name, path

        assert request.input.github_url is not None
        match = GITHUB_REPO_PATTERN.search(request.input.github_url)
        if not match:
            return "unknown-repo", self.workspace_root / f"unknown-repo-{run_id}"
        repo_name = match.group("repo")
        return repo_name, self.workspace_root / f"{repo_name}-{run_id}"

    @staticmethod
    def _resolve_git_sha(repo_path: Path) -> str | None:
        if not repo_path.exists():
            return None
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    @staticmethod
    def _package_version(package_name: str) -> str:
        try:
            return version(package_name)
        except PackageNotFoundError:
            return "unknown"

    @staticmethod
    def _tool_version(cmd: list[str]) -> str | None:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None
        if result.returncode != 0:
            return None
        first_line = result.stdout.strip().splitlines()
        if not first_line:
            return None
        return first_line[0]


class RunManifestStore:
    """SQLite persistence for run manifests."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_manifests (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def upsert(self, manifest: RunManifest) -> None:
        payload_json = orjson.dumps(manifest.model_dump(mode="json")).decode("utf-8")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO run_manifests (run_id, created_at, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (manifest.run_id, manifest.created_at, payload_json),
            )

    def get(self, run_id: str) -> RunManifest | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM run_manifests WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RunManifest.model_validate_json(row[0])
