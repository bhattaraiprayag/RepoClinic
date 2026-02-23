"""Tool runner robustness tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import repoclinic.scanner.tool_runners as tool_runner_module
from repoclinic.scanner.pipeline import _resolve_dependency_status
from repoclinic.scanner.tool_runners import ToolRunResult, ToolRunners


def test_bandit_command_uses_quiet_and_excludes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Bandit command should run in quiet mode and exclude noisy paths."""
    captured: dict[str, object] = {}

    def _fake_run_json_command(
        self,  # noqa: ANN001
        *,
        tool_name: str,
        cmd: list[str],
        success_codes: set[int],
        unavailable_codes: set[int] | None = None,
        cwd: Path | None = None,
    ) -> ToolRunResult:
        captured["tool_name"] = tool_name
        captured["cmd"] = cmd
        captured["success_codes"] = success_codes
        captured["unavailable_codes"] = unavailable_codes
        captured["cwd"] = cwd
        return ToolRunResult(status="completed", payload={})

    monkeypatch.setattr(ToolRunners, "_run_json_command", _fake_run_json_command)
    ToolRunners(timeout_seconds=10).run_bandit(Path("/tmp/repo"))

    assert captured["tool_name"] == "bandit"
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "-q" in cmd
    assert "-x" in cmd
    exclude_arg = cmd[cmd.index("-x") + 1]
    assert ".scanner-workspace" not in exclude_arg
    assert captured["cwd"] == Path("/tmp/repo")


def test_osv_command_uses_no_ignore_by_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """OSV command should include --no-ignore to avoid hidden-path dropouts."""
    captured: dict[str, object] = {}

    def _fake_run_json_command(
        self,  # noqa: ANN001
        *,
        tool_name: str,
        cmd: list[str],
        success_codes: set[int],
        unavailable_codes: set[int] | None = None,
        cwd: Path | None = None,
    ) -> ToolRunResult:
        captured["tool_name"] = tool_name
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return ToolRunResult(status="completed", payload={})

    monkeypatch.setattr(ToolRunners, "_run_json_command", _fake_run_json_command)
    ToolRunners(timeout_seconds=10).run_osv(Path("/tmp/repo"))

    assert captured["tool_name"] == "osv-scanner"
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "--no-ignore" in cmd
    assert captured["cwd"] == Path("/tmp/repo")


def test_osv_exit_code_128_maps_to_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """OSV exit code 128 should be treated as unavailable scan context."""
    monkeypatch.setattr(
        tool_runner_module.shutil, "which", lambda _name: "/usr/bin/osv"
    )
    monkeypatch.setattr(
        tool_runner_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=128, stdout="", stderr="no packages found"
        ),
    )

    result = ToolRunners(timeout_seconds=10).run_osv(Path("/tmp/repo"))
    assert result.status == "unavailable"
    assert result.exit_code == 128


def test_extract_json_payload_handles_preamble() -> None:
    """JSON parser should recover payloads with non-JSON preamble."""
    payload = ToolRunners._extract_json_payload('warning line\n{"results": []}')
    assert payload == {"results": []}


def test_dependency_status_prioritizes_completed() -> None:
    """Dependency status should remain completed when at least one run completed."""
    assert _resolve_dependency_status([]) == "unavailable"
    assert _resolve_dependency_status(["unavailable"]) == "unavailable"
    assert _resolve_dependency_status(["failed"]) == "failed"
    assert _resolve_dependency_status(["completed", "failed"]) == "completed"


def test_normalize_lockfiles_keeps_existing_relative_paths(tmp_path: Path) -> None:
    """Lockfile normalization should keep in-repo files and ignore external ones."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "uv.lock").write_text("content", encoding="utf-8")
    outside = tmp_path / "outside.lock"
    outside.write_text("x", encoding="utf-8")

    normalized = ToolRunners._normalize_lockfiles(
        repo,
        [
            "uv.lock",
            str((repo / "uv.lock").resolve()),
            str(outside.resolve()),
            "missing.lock",
        ],
    )
    assert normalized == ["uv.lock"]


def test_osv_falls_back_to_lockfile_scan(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """OSV should retry recursive scanning when lockfile-only mode is unavailable."""
    repo = tmp_path / "repo"
    repo.mkdir()
    lockfile = repo / "uv.lock"
    lockfile.write_text("content", encoding="utf-8")
    calls: list[list[str]] = []

    def _fake_run_json_command(
        self,  # noqa: ANN001
        *,
        tool_name: str,
        cmd: list[str],
        success_codes: set[int],
        unavailable_codes: set[int] | None = None,
        cwd: Path | None = None,
    ) -> ToolRunResult:
        del self, tool_name, success_codes, unavailable_codes, cwd
        calls.append(cmd)
        if "-L" in cmd:
            return ToolRunResult(
                status="unavailable", payload={}, error="no package sources"
            )
        return ToolRunResult(status="completed", payload={"results": []}, exit_code=0)

    monkeypatch.setattr(ToolRunners, "_run_json_command", _fake_run_json_command)
    result = ToolRunners(timeout_seconds=10).run_osv(
        repo,
        lockfiles=["uv.lock", str(lockfile.resolve())],
    )

    assert result.status == "completed"
    assert len(calls) == 2
    assert "-L" in calls[0]
    assert "-r" in calls[1]
