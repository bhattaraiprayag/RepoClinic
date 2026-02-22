"""CLI for RepoClinic."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from repoclinic.agents import HeuristicBranchExecutor
from repoclinic.config import load_app_config
from repoclinic.constants import PACKAGE_VERSION
from repoclinic.flow import RepoClinicFlowRunner
from repoclinic.schemas.input_models import (
    AnalyzeInput,
    AnalyzeRequest,
    ExecutionConfig,
    FeatureFlags,
    ProviderConfig,
    TimeoutConfig,
)
from repoclinic.schemas.output_models import AnalysisStatus
from repoclinic.security.redaction import redact_text

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="RepoClinic deterministic repository analysis pipeline.",
)
console = Console()


@app.command()
def version() -> None:
    """Print the RepoClinic version."""
    typer.echo(PACKAGE_VERSION)


@app.command("validate-config")
def validate_config(
    config: Path | None = typer.Option(
        None, "--config", help="Path to settings.yaml override."
    ),
) -> None:
    """Validate configuration and print provider profiles."""
    try:
        config_model = load_app_config(config)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Configuration validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="Provider Profiles")
    table.add_column("Profile")
    table.add_column("Type")
    table.add_column("Model")
    table.add_column("Base URL")
    table.add_column("Context Window", justify="right")
    for profile_name, profile in config_model.provider_profiles.items():
        table.add_row(
            profile_name,
            profile.provider_type.value,
            profile.model,
            profile.base_url or "-",
            str(profile.capabilities.context_window),
        )
    console.print(table)


@app.command("analyze")
def analyze(
    repo: str | None = typer.Option(None, "--repo", help="GitHub repository URL."),
    local_path: Path | None = typer.Option(
        None, "--path", help="Local repository path."
    ),
    branch: str | None = typer.Option(None, "--branch", help="Git branch to check out."),
    commit: str | None = typer.Option(None, "--commit", help="Git commit SHA to check out."),
    provider_profile: str | None = typer.Option(
        None, "--provider-profile", help="Provider profile name from config."
    ),
    branch_executor: str = typer.Option(
        "crewai",
        "--branch-executor",
        help="Branch executor mode: crewai or heuristic.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts"), "--output-dir", help="Directory for report artifacts."
    ),
    config: Path | None = typer.Option(None, "--config", help="Path to settings.yaml override."),
    db_path: Path = typer.Option(
        Path(".sqlite/repoclinic.db"), "--db-path", help="SQLite path for flow state."
    ),
    workspace_root: Path = typer.Option(
        Path(".scanner-workspace"), "--workspace-root", help="Workspace root for cloned repos."
    ),
) -> None:
    """Run full ARC-FL2 analysis and generate report artifacts."""
    try:
        _ensure_single_input(repo=repo, local_path=local_path)
        runner = RepoClinicFlowRunner(
            config_path=config,
            db_path=db_path,
            workspace_root=workspace_root,
        )
        profile_name = _resolve_provider_profile(runner, provider_profile)
        request = _build_request(
            runner=runner,
            profile_name=profile_name,
            repo=repo,
            local_path=local_path,
            branch=branch,
            commit=commit,
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task(description="Running ARC-FL2 flow", total=None)
            state = runner.kickoff(
                request=request,
                provider_profile=profile_name,
                branch_executor=_resolve_branch_executor(branch_executor),
            )

        artifacts = runner.materialize_artifacts(state=state, output_dir=output_dir)
        _render_status_panel(artifacts.summary.analysis_status)
        _render_artifact_paths(artifacts.summary_path, artifacts.report_path)
        _raise_on_hard_failure(artifacts.summary.analysis_status)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Analysis failed:[/red] {redact_text(str(exc))}")
        raise typer.Exit(code=1) from exc


@app.command("resume")
def resume(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to resume."),
    provider_profile: str | None = typer.Option(
        None, "--provider-profile", help="Provider profile name from config."
    ),
    branch_executor: str = typer.Option(
        "crewai",
        "--branch-executor",
        help="Branch executor mode: crewai or heuristic.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts"), "--output-dir", help="Directory for report artifacts."
    ),
    config: Path | None = typer.Option(None, "--config", help="Path to settings.yaml override."),
    db_path: Path = typer.Option(
        Path(".sqlite/repoclinic.db"), "--db-path", help="SQLite path for flow state."
    ),
    workspace_root: Path = typer.Option(
        Path(".scanner-workspace"), "--workspace-root", help="Workspace root for cloned repos."
    ),
) -> None:
    """Resume a checkpointed ARC-FL2 run and regenerate artifacts."""
    try:
        runner = RepoClinicFlowRunner(
            config_path=config,
            db_path=db_path,
            workspace_root=workspace_root,
        )
        profile_name = _resolve_provider_profile(runner, provider_profile)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task(description="Resuming ARC-FL2 flow", total=None)
            state = runner.resume(
                run_id=run_id,
                provider_profile=profile_name,
                branch_executor=_resolve_branch_executor(branch_executor),
            )

        artifacts = runner.materialize_artifacts(state=state, output_dir=output_dir)
        _render_status_panel(artifacts.summary.analysis_status)
        _render_artifact_paths(artifacts.summary_path, artifacts.report_path)
        _raise_on_hard_failure(artifacts.summary.analysis_status)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Resume failed:[/red] {redact_text(str(exc))}")
        raise typer.Exit(code=1) from exc


@app.command("healthcheck")
def healthcheck(
    config: Path | None = typer.Option(None, "--config", help="Path to settings.yaml override."),
    db_path: Path = typer.Option(
        Path(".sqlite/repoclinic.db"), "--db-path", help="SQLite path for flow state."
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress success output."),
) -> None:
    """Validate runtime readiness for deployment health probes."""
    try:
        cfg = load_app_config(config)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch(exist_ok=True)
        if not quiet:
            console.print(
                f"[green]OK[/green] provider={cfg.default_provider_profile} db={db_path}"
            )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Healthcheck failed:[/red] {redact_text(str(exc))}")
        raise typer.Exit(code=1) from exc


def _ensure_single_input(*, repo: str | None, local_path: Path | None) -> None:
    if bool(repo) == bool(local_path):
        raise typer.BadParameter("Provide exactly one of --repo or --path.")


def _resolve_provider_profile(
    runner: RepoClinicFlowRunner,
    provider_profile: str | None,
) -> str:
    profile_name = provider_profile or runner.config.default_provider_profile
    if profile_name not in runner.config.provider_profiles:
        raise typer.BadParameter(f"Unknown provider profile: {profile_name}")
    return profile_name


def _build_request(
    *,
    runner: RepoClinicFlowRunner,
    profile_name: str,
    repo: str | None,
    local_path: Path | None,
    branch: str | None,
    commit: str | None,
) -> AnalyzeRequest:
    profile = runner.config.provider_profiles[profile_name]
    source_type = "github_url" if repo else "local_path"
    analyze_input = AnalyzeInput(
        source_type=source_type,
        github_url=repo,
        local_path=str(local_path) if local_path else None,
        branch=branch,
        commit=commit,
    )
    execution = ExecutionConfig(
        provider=ProviderConfig(
            type=profile.provider_type,
            model=profile.model,
            temperature=profile.temperature,
            seed=profile.seed,
            max_tokens=profile.max_tokens,
        ),
        timeouts=TimeoutConfig(
            scanner_seconds=runner.config.timeouts.scanner_seconds,
            agent_seconds=runner.config.timeouts.agent_seconds,
        ),
        feature_flags=FeatureFlags(
            enable_tree_sitter=runner.config.feature_flags.enable_tree_sitter,
            enable_bandit=runner.config.feature_flags.enable_bandit,
            enable_semgrep=runner.config.feature_flags.enable_semgrep,
            enable_osv=runner.config.feature_flags.enable_osv,
        ),
    )
    return AnalyzeRequest(
        schema_version=runner.config.schema_version,
        run_id=str(uuid4()),
        input=analyze_input,
        execution=execution,
    )


def _render_status_panel(status: AnalysisStatus) -> None:
    table = Table(title="Analysis Status")
    table.add_column("Stage")
    table.add_column("Status")
    status_payload: dict[str, Any] = status.model_dump(mode="json")
    for stage in ("scanner", "architecture", "security", "performance", "roadmap"):
        table.add_row(stage, status_payload[stage])
    console.print(table)


def _render_artifact_paths(summary_path: Path, report_path: Path) -> None:
    panel = Panel.fit(
        f"summary.json: [bold]{summary_path}[/bold]\nreport.md: [bold]{report_path}[/bold]",
        title="Artifacts Generated",
    )
    console.print(panel)


def _raise_on_hard_failure(status: AnalysisStatus) -> None:
    if status.scanner == "failed" or status.roadmap == "failed":
        raise typer.Exit(code=1)


def _resolve_branch_executor(mode: str):  # noqa: ANN201
    normalized = mode.strip().lower()
    if normalized == "crewai":
        return None
    if normalized == "heuristic":
        return HeuristicBranchExecutor()
    raise typer.BadParameter("branch-executor must be either 'crewai' or 'heuristic'.")
