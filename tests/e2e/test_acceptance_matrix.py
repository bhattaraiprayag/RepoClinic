"""Phase 9 acceptance matrix tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import repoclinic.cli as cli_module
from repoclinic.schemas.output_models import SummaryJson


def _write_config(tmp_path: Path, *, max_file_size_bytes: int = 100000) -> Path:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        f"""
schema_version: "1.0.0"
default_provider_profile: "openai-default"
provider_profiles:
  openai-default:
    provider_type: "openai"
    model: "gpt-4.1"
    api_key_env: "OPENAI_API_KEY"
    max_tokens: 1024
    timeout_seconds: 60
    capabilities:
      context_window: 128000
      supports_structured_output: true
      retries: 2
  lm-studio-default:
    provider_type: "lm_studio"
    model: "qwen/qwen3-vl-30b"
    api_key_env: "LM_STUDIO_AUTH_TOKEN"
    base_url: "http://127.0.0.1:1234/v1"
    max_tokens: 1024
    timeout_seconds: 60
    capabilities:
      context_window: 16384
      supports_structured_output: true
      retries: 2
retries:
  max_attempts: 2
  backoff_seconds: 0.01
  jitter_seconds: 0.0
timeouts:
  scanner_seconds: 30
  agent_seconds: 30
feature_flags:
  enable_tree_sitter: false
  enable_bandit: false
  enable_semgrep: false
  enable_osv: false
scan_policy:
  include_globs:
    - "**/*"
  exclude_globs:
    - ".git/**"
    - "node_modules/**"
    - "dist/**"
  max_file_size_bytes: {max_file_size_bytes}
  max_files: 5000
""".strip(),
        encoding="utf-8",
    )
    return config_path


def _load_summary(path: Path) -> SummaryJson:
    return SummaryJson.model_validate_json(path.read_text(encoding="utf-8"))


def test_acceptance_small_multilanguage_repo(tmp_path: Path) -> None:
    """Small multi-language fixture should produce valid report artifacts."""
    fixture_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    config_path = _write_config(tmp_path)
    output_dir = tmp_path / "artifacts-small"
    runner = CliRunner()

    result = runner.invoke(
        cli_module.app,
        [
            "analyze",
            "--path",
            str(fixture_repo),
            "--config",
            str(config_path),
            "--branch-executor",
            "heuristic",
            "--output-dir",
            str(output_dir),
            "--db-path",
            str(tmp_path / "flow.db"),
            "--workspace-root",
            str(tmp_path / "workspace"),
        ],
    )
    assert result.exit_code == 0
    summary = _load_summary(output_dir / "summary.json")
    assert "Python" in summary.language_detected
    assert "JavaScript" in summary.language_detected
    assert (output_dir / "report.md").exists()


def test_acceptance_large_repo_handles_skip_limits(tmp_path: Path) -> None:
    """Large-file scenario should still complete and emit valid artifacts."""
    repo_path = tmp_path / "large-repo"
    repo_path.mkdir()
    (repo_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_path / "large.txt").write_text("x" * 10000, encoding="utf-8")
    config_path = _write_config(tmp_path, max_file_size_bytes=200)
    output_dir = tmp_path / "artifacts-large"
    runner = CliRunner()

    result = runner.invoke(
        cli_module.app,
        [
            "analyze",
            "--path",
            str(repo_path),
            "--config",
            str(config_path),
            "--branch-executor",
            "heuristic",
            "--output-dir",
            str(output_dir),
            "--db-path",
            str(tmp_path / "flow.db"),
            "--workspace-root",
            str(tmp_path / "workspace"),
        ],
    )
    assert result.exit_code == 0
    summary = _load_summary(output_dir / "summary.json")
    assert summary.repo_name == "large-repo"
    report = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "Files skipped:" in report


def test_acceptance_partial_failure_produces_degraded_summary(tmp_path: Path) -> None:
    """Missing provider key should degrade branches but keep synthesis output."""
    fixture_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    config_path = _write_config(tmp_path)
    output_dir = tmp_path / "artifacts-degraded"
    runner = CliRunner()

    result = runner.invoke(
        cli_module.app,
        [
            "analyze",
            "--path",
            str(fixture_repo),
            "--config",
            str(config_path),
            "--branch-executor",
            "crewai",
            "--output-dir",
            str(output_dir),
            "--db-path",
            str(tmp_path / "flow.db"),
            "--workspace-root",
            str(tmp_path / "workspace"),
        ],
        env={"OPENAI_API_KEY": ""},
    )
    assert result.exit_code == 0
    summary = _load_summary(output_dir / "summary.json")
    assert summary.analysis_status.roadmap == "degraded"
    assert summary.analysis_status.security in {"failed", "degraded"}


def test_acceptance_deterministic_rerun(tmp_path: Path) -> None:
    """Repeated deterministic-branch runs should produce stable summary payloads."""
    fixture_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    config_path = _write_config(tmp_path)
    runner = CliRunner()
    output_a = tmp_path / "out-a"
    output_b = tmp_path / "out-b"

    for output_dir in (output_a, output_b):
        result = runner.invoke(
            cli_module.app,
            [
                "analyze",
                "--path",
                str(fixture_repo),
                "--config",
                str(config_path),
                "--branch-executor",
                "heuristic",
                "--output-dir",
                str(output_dir),
                "--db-path",
                str(tmp_path / f"{output_dir.name}.db"),
                "--workspace-root",
                str(tmp_path / "workspace"),
            ],
        )
        assert result.exit_code == 0

    summary_a = json.loads((output_a / "summary.json").read_text(encoding="utf-8"))
    summary_b = json.loads((output_b / "summary.json").read_text(encoding="utf-8"))
    summary_a.pop("run_id", None)
    summary_b.pop("run_id", None)
    assert summary_a == summary_b
