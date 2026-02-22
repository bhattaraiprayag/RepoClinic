"""Phase 7 CLI workflow tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import repoclinic.cli as cli_module
from repoclinic.artifacts.generator import write_artifacts
from repoclinic.config import load_app_config
from repoclinic.schemas.enums import ArchitectureType
from repoclinic.schemas.output_models import AnalysisStatus, SummaryJson


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
schema_version: "1.0.0"
default_provider_profile: "openai-default"
provider_profiles:
  openai-default:
    provider_type: "openai"
    model: "gpt-4.1"
    api_key_env: "OPENAI_API_KEY"
    max_tokens: 1024
    capabilities:
      context_window: 128000
  lm-studio-default:
    provider_type: "lm_studio"
    model: "qwen/qwen3-vl-30b"
    api_key_env: "LM_STUDIO_AUTH_TOKEN"
    base_url: "http://127.0.0.1:1234/v1"
    max_tokens: 1024
    capabilities:
      context_window: 16384
""".strip(),
        encoding="utf-8",
    )
    return config_path


class _FakeRunner:
    def __init__(
        self,
        *,
        config_path: Path | None = None,
        db_path: Path | None = None,
        workspace_root: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        del db_path, workspace_root, env
        self.config = load_app_config(config_path, env={})

    def kickoff(self, **kwargs: object) -> object:  # noqa: ANN003
        del kwargs
        return object()

    def resume(self, **kwargs: object) -> object:  # noqa: ANN003
        del kwargs
        return object()

    def materialize_artifacts(self, *, state: object, output_dir: Path):  # noqa: ANN201
        del state
        summary = SummaryJson(
            schema_version="1.0.0",
            run_id="run-cli",
            repo_name="sample-repo",
            language_detected=["Python"],
            frameworks=["FastAPI"],
            architecture_type=ArchitectureType.MONOLITH,
            top_security_risks=[],
            top_performance_risks=[],
            roadmap=[],
            analysis_status=AnalysisStatus(
                scanner="completed",
                architecture="completed",
                security="completed",
                performance="completed",
                roadmap="completed",
            ),
        )
        return write_artifacts(
            output_dir=output_dir,
            summary=summary,
            report_markdown="# Repository Analysis Report\n\n## Repository Overview\n",
        )


def test_analyze_requires_repo_or_path() -> None:
    """Analyze should reject missing --repo/--path inputs."""
    runner = CliRunner()
    result = runner.invoke(cli_module.app, ["analyze"])
    assert result.exit_code != 0
    assert "Provide exactly one of --repo or --path." in result.stdout


def test_analyze_creates_artifacts(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Analyze command should write summary.json and report.md."""
    monkeypatch.setattr(cli_module, "RepoClinicFlowRunner", _FakeRunner)
    config_path = _write_config(tmp_path)
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    output_dir = tmp_path / "out"

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "analyze",
            "--path",
            str(repo_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "report.md").exists()


def test_resume_creates_artifacts(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Resume should regenerate artifacts by run id."""
    monkeypatch.setattr(cli_module, "RepoClinicFlowRunner", _FakeRunner)
    config_path = _write_config(tmp_path)
    output_dir = tmp_path / "resume-out"

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "resume",
            "--run-id",
            "run-123",
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "report.md").exists()


def test_validate_config_lists_profiles(tmp_path: Path) -> None:
    """validate-config should load and print provider profiles."""
    config_path = _write_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli_module.app, ["validate-config", "--config", str(config_path)]
    )
    assert result.exit_code == 0
    assert "openai-default" in result.stdout
    assert "lm_studio" in result.stdout
