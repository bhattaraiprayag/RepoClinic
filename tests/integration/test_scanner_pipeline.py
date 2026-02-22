"""Integration tests for deterministic scanner pipeline."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from repoclinic.config.models import AppConfig
from repoclinic.scanner.pipeline import ScannerPipeline
from repoclinic.scanner.tool_runners import ToolRunResult
from repoclinic.schemas.input_models import (
    AnalyzeInput,
    AnalyzeRequest,
    ExecutionConfig,
    FeatureFlags,
    ProviderConfig,
    TimeoutConfig,
)


def _build_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "default_provider_profile": "openai-default",
            "provider_profiles": {
                "openai-default": {
                    "provider_type": "openai",
                    "model": "gpt-4.1",
                    "api_key_env": "OPENAI_API_KEY",
                    "max_tokens": 1024,
                    "capabilities": {
                        "context_window": 128000,
                        "supports_structured_output": True,
                        "retries": 3,
                    },
                }
            },
            "scan_policy": {
                "include_globs": ["**/*"],
                "exclude_globs": [".git/**", "node_modules/**", "dist/**"],
                "max_file_size_bytes": 100000,
                "max_files": 5000,
            },
        }
    )


def test_scanner_pipeline_outputs_valid_payload_and_persists(tmp_path: Path) -> None:
    """Scanner should produce schema-valid output and SQLite checkpoint."""
    fixture_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    db_path = tmp_path / "scanner.db"
    pipeline = ScannerPipeline(
        config=_build_config(),
        workspace_root=tmp_path / "workspace",
        db_path=db_path,
    )
    request = AnalyzeRequest(
        schema_version="1.0.0",
        run_id="run-test-1",
        input=AnalyzeInput(source_type="local_path", local_path=str(fixture_repo)),
        execution=ExecutionConfig(
            provider=ProviderConfig(type="openai", model="gpt-4.1"),
            timeouts=TimeoutConfig(scanner_seconds=10, agent_seconds=10),
            feature_flags=FeatureFlags(
                enable_semgrep=False,
                enable_bandit=False,
                enable_osv=False,
                enable_tree_sitter=False,
            ),
        ),
    )

    output = pipeline.run(request)

    assert output.repo_profile.repo_name == "sample_repo"
    assert "Python" in output.repo_profile.languages_detected
    assert "JavaScript" in output.repo_profile.languages_detected
    assert "FastAPI" in output.repo_profile.frameworks_detected
    assert any("package.json" in manifest for manifest in output.repo_profile.manifests)
    assert output.scan_stats.skipped_reasons.ignored_pathspec >= 1
    assert output.evidence_index

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT run_id FROM scanner_outputs WHERE run_id = ?", ("run-test-1",)
        ).fetchone()
    assert row == ("run-test-1",)


def test_scanner_pipeline_collects_lockfiles_for_osv(
    monkeypatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    """OSV runner should receive normalized lockfile paths discovered by inventory."""
    fixture_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    captured: dict[str, list[str]] = {}

    def _fake_run_osv(
        self, repo_path: Path, *, lockfiles: list[str] | None = None
    ) -> ToolRunResult:  # noqa: ANN001
        del self, repo_path
        captured["lockfiles"] = lockfiles or []
        return ToolRunResult(status="completed", payload={"results": []}, exit_code=0)

    monkeypatch.setattr(
        "repoclinic.scanner.tool_runners.ToolRunners.run_osv",
        _fake_run_osv,
    )

    pipeline = ScannerPipeline(
        config=_build_config(),
        workspace_root=tmp_path / "workspace",
        db_path=tmp_path / "scanner.db",
    )
    request = AnalyzeRequest(
        schema_version="1.0.0",
        run_id="run-test-osv-lockfiles",
        input=AnalyzeInput(source_type="local_path", local_path=str(fixture_repo)),
        execution=ExecutionConfig(
            provider=ProviderConfig(type="openai", model="gpt-4.1"),
            timeouts=TimeoutConfig(scanner_seconds=10, agent_seconds=10),
            feature_flags=FeatureFlags(
                enable_semgrep=False,
                enable_bandit=False,
                enable_osv=True,
                enable_tree_sitter=False,
            ),
        ),
    )

    pipeline.run(request)
    assert "requirements.txt" in captured["lockfiles"]
