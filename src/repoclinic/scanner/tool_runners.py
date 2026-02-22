"""Deterministic wrappers around Semgrep/Bandit/OSV scanners."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ToolRunStatus = Literal["completed", "failed", "unavailable"]
DEFAULT_BANDIT_EXCLUDES = [
    ".git",
    "node_modules",
    "dist",
    ".venv",
    "__pycache__",
    "tests/fixtures",
]


@dataclass(frozen=True)
class ToolRunResult:
    """Normalized command execution result."""

    status: ToolRunStatus
    payload: dict[str, Any]
    error: str | None = None
    exit_code: int | None = None
    stderr: str | None = None


class ToolRunners:
    """Runs external scanners with deterministic JSON handling."""

    def __init__(
        self,
        timeout_seconds: int,
        *,
        bandit_excludes: list[str] | None = None,
        osv_no_ignore: bool = True,
        osv_fallback_lockfile_scan: bool = True,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.bandit_excludes = bandit_excludes or DEFAULT_BANDIT_EXCLUDES
        self.osv_no_ignore = osv_no_ignore
        self.osv_fallback_lockfile_scan = osv_fallback_lockfile_scan

    def run_semgrep(self, repo_path: Path) -> ToolRunResult:
        return self._run_json_command(
            tool_name="semgrep",
            cmd=["semgrep", "scan", "--config", "auto", "--json", "."],
            success_codes={0, 1},
            cwd=repo_path,
        )

    def run_bandit(self, repo_path: Path) -> ToolRunResult:
        excluded_paths = ",".join(self.bandit_excludes)
        return self._run_json_command(
            tool_name="bandit",
            cmd=[
                "bandit",
                "-q",
                "-r",
                ".",
                "-f",
                "json",
                "-x",
                excluded_paths,
            ],
            success_codes={0, 1},
            cwd=repo_path,
        )

    def run_osv(
        self, repo_path: Path, *, lockfiles: list[str] | None = None
    ) -> ToolRunResult:
        cmd = ["osv-scanner", "scan", "source", "-r", ".", "--format", "json"]
        if self.osv_no_ignore:
            cmd.insert(5, "--no-ignore")
        primary = self._run_json_command(
            tool_name="osv-scanner",
            cmd=cmd,
            success_codes={0, 1},
            unavailable_codes={128},
            cwd=repo_path,
        )
        if (
            primary.status == "completed"
            or not self.osv_fallback_lockfile_scan
            or not lockfiles
        ):
            return primary
        lockfile_args = self._normalize_lockfiles(repo_path, lockfiles)
        if not lockfile_args:
            return primary
        fallback_cmd = ["osv-scanner", "scan", "source", "--format", "json"]
        if self.osv_no_ignore:
            fallback_cmd.append("--no-ignore")
        for lockfile in lockfile_args:
            fallback_cmd.extend(["-L", lockfile])
        fallback = self._run_json_command(
            tool_name="osv-scanner",
            cmd=fallback_cmd,
            success_codes={0, 1},
            unavailable_codes={128},
            cwd=repo_path,
        )
        if fallback.status == "completed":
            return fallback
        if primary.error and fallback.error:
            status: ToolRunStatus = (
                "failed"
                if "failed" in {primary.status, fallback.status}
                else "unavailable"
            )
            return ToolRunResult(
                status=status,
                payload={},
                error=f"{primary.error}; fallback: {fallback.error}",
                exit_code=fallback.exit_code or primary.exit_code,
                stderr=fallback.stderr or primary.stderr,
            )
        return primary

    def _run_json_command(
        self,
        *,
        tool_name: str,
        cmd: list[str],
        success_codes: set[int],
        unavailable_codes: set[int] | None = None,
        cwd: Path | None = None,
    ) -> ToolRunResult:
        if shutil.which(tool_name) is None:
            return ToolRunResult(
                status="unavailable",
                payload={},
                error=f"{tool_name} not found",
            )

        unavailable_codes = unavailable_codes or set()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            return ToolRunResult(
                status="failed",
                payload={},
                error=f"{tool_name} timed out",
            )

        if result.returncode in unavailable_codes:
            message = (
                result.stderr.strip()
                or result.stdout.strip()
                or (f"{tool_name} reported unavailable scan context")
            )
            return ToolRunResult(
                status="unavailable",
                payload={},
                error=message,
                exit_code=result.returncode,
                stderr=result.stderr.strip() or None,
            )

        if result.returncode not in success_codes:
            return ToolRunResult(
                status="failed",
                payload={},
                error=result.stderr.strip() or f"{tool_name} failed",
                exit_code=result.returncode,
                stderr=result.stderr.strip() or None,
            )

        stdout = result.stdout.strip()
        if not stdout:
            return ToolRunResult(
                status="completed",
                payload={},
                exit_code=result.returncode,
                stderr=result.stderr.strip() or None,
            )

        payload = self._extract_json_payload(stdout)
        if payload is None:
            return ToolRunResult(
                status="failed",
                payload={},
                error=f"{tool_name} produced non-JSON output",
                exit_code=result.returncode,
                stderr=result.stderr.strip() or None,
            )
        return ToolRunResult(
            status="completed",
            payload=payload,
            exit_code=result.returncode,
            stderr=result.stderr.strip() or None,
        )

    @staticmethod
    def _normalize_lockfiles(repo_path: Path, lockfiles: list[str]) -> list[str]:
        repo_root = repo_path.resolve()
        normalized: list[str] = []
        seen: set[str] = set()
        for lockfile in sorted(lockfiles):
            candidate = Path(lockfile)
            lockfile_path = (
                candidate if candidate.is_absolute() else repo_root / candidate
            )
            if not lockfile_path.exists() or lockfile_path.is_dir():
                continue
            try:
                relative = lockfile_path.resolve().relative_to(repo_root)
            except ValueError:
                continue
            relative_str = str(relative)
            if relative_str in seen:
                continue
            seen.add(relative_str)
            normalized.append(relative_str)
        return normalized

    @staticmethod
    def _extract_json_payload(stdout: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(stdout)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        start = stdout.find("{")
        while start != -1:
            try:
                payload, _ = decoder.raw_decode(stdout[start:])
            except json.JSONDecodeError:
                start = stdout.find("{", start + 1)
                continue
            if isinstance(payload, dict):
                return payload
            start = stdout.find("{", start + 1)
        return None
