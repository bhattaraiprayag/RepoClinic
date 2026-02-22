"""Source resolver path normalization tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from repoclinic.scanner.source_resolver import SourceResolver
from repoclinic.schemas.input_models import AnalyzeInput


def test_local_path_resolves_to_absolute_path(tmp_path: Path) -> None:
    """Local input should always resolve to an absolute directory path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    resolver = SourceResolver(tmp_path / "workspace")

    resolved = resolver.resolve(
        AnalyzeInput(source_type="local_path", local_path=str(repo)),
        run_id="run-1",
    )

    assert resolved.source_type == "local_path"
    assert resolved.repo_name == "repo"
    assert resolved.resolved_path == repo.resolve()
    assert resolved.resolved_path.is_absolute()


def test_github_clone_destination_is_absolute(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """GitHub source should resolve to an absolute clone destination path."""
    resolver = SourceResolver(tmp_path / "workspace")
    captured_cmd: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured_cmd["cmd"] = cmd
        destination = Path(cmd[-1])
        destination.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    resolved = resolver.resolve(
        AnalyzeInput(
            source_type="github_url",
            github_url="https://github.com/org/repo",
        ),
        run_id="run-2",
    )

    assert captured_cmd["cmd"][0:2] == ["git", "clone"]
    assert resolved.source_type == "github_url"
    assert resolved.repo_name == "repo"
    assert resolved.resolved_path.is_absolute()
    assert resolved.resolved_path == (tmp_path / "workspace" / "repo-run-2").resolve()
