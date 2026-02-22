"""Deterministic wrappers around Semgrep/Bandit/OSV scanners."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ToolRunStatus = Literal["completed", "failed", "unavailable"]


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

    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def run_semgrep(self, repo_path: Path) -> ToolRunResult:
        return self._run_json_command(
            tool_name="semgrep",
            cmd=["semgrep", "scan", "--config", "auto", "--json", str(repo_path)],
            success_codes={0, 1},
        )

    def run_bandit(self, repo_path: Path) -> ToolRunResult:
        excluded_paths = ",".join(
            [
                ".git",
                "node_modules",
                "dist",
                ".venv",
                "__pycache__",
                "tests/fixtures",
                ".scanner-workspace",
            ]
        )
        return self._run_json_command(
            tool_name="bandit",
            cmd=[
                "bandit",
                "-q",
                "-r",
                str(repo_path),
                "-f",
                "json",
                "-x",
                excluded_paths,
            ],
            success_codes={0, 1},
        )

    def run_osv(self, repo_path: Path) -> ToolRunResult:
        return self._run_json_command(
            tool_name="osv-scanner",
            cmd=[
                "osv-scanner",
                "scan",
                "source",
                "-r",
                str(repo_path),
                "--format",
                "json",
            ],
            success_codes={0, 1},
            unavailable_codes={128},
        )

    def _run_json_command(
        self,
        *,
        tool_name: str,
        cmd: list[str],
        success_codes: set[int],
        unavailable_codes: set[int] | None = None,
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
