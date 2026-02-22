"""Phase 8 run manifest capture tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from repoclinic.agents.executor import HeuristicBranchExecutor
from repoclinic.flow.repoclinic_flow import RepoClinicFlowRunner
from repoclinic.schemas.input_models import (
    AnalyzeInput,
    AnalyzeRequest,
    ExecutionConfig,
    FeatureFlags,
    ProviderConfig,
    TimeoutConfig,
)


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
    timeout_seconds: 60
    capabilities:
      context_window: 128000
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
  max_file_size_bytes: 100000
  max_files: 5000
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_run_manifest_persists_metadata(tmp_path: Path) -> None:
    """Runner should capture and persist metadata completeness envelope."""
    config_path = _write_config(tmp_path)
    fixture_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    run_id = str(uuid4())
    runner = RepoClinicFlowRunner(
        config_path=config_path,
        db_path=tmp_path / "flow.db",
        workspace_root=tmp_path / "workspace",
        env={},
    )
    request = AnalyzeRequest(
        schema_version="1.0.0",
        run_id=run_id,
        input=AnalyzeInput(source_type="local_path", local_path=str(fixture_repo)),
        execution=ExecutionConfig(
            provider=ProviderConfig(type="openai", model="gpt-4.1"),
            timeouts=TimeoutConfig(scanner_seconds=30, agent_seconds=30),
            feature_flags=FeatureFlags(
                enable_tree_sitter=False,
                enable_bandit=False,
                enable_semgrep=False,
                enable_osv=False,
            ),
        ),
    )
    state = runner.kickoff(
        request=request,
        provider_profile="openai-default",
        branch_executor=HeuristicBranchExecutor(),
    )
    manifest = runner.manifest_store.get(run_id)
    assert manifest is not None
    assert manifest.run_id == run_id
    assert manifest.repo.repo_name == fixture_repo.name
    assert manifest.provider.profile == "openai-default"
    assert manifest.tool_versions.crewai
    assert manifest.tool_versions.python
    assert manifest.prompt_versions.roadmap
    assert manifest.timeouts.scanner_seconds == 30
    assert "scanner" in manifest.analysis_status
    assert state.run_manifest is not None
