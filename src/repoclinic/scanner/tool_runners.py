"""Deterministic wrappers around Semgrep/Bandit/OSV scanners."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolRunResult:
    """Normalized command execution result."""

    status: str
    payload: dict[str, Any]
    error: str | None = None


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
        return self._run_json_command(
            tool_name="bandit",
            cmd=["bandit", "-r", str(repo_path), "-f", "json"],
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
        )

    def _run_json_command(
        self,
        *,
        tool_name: str,
        cmd: list[str],
        success_codes: set[int],
    ) -> ToolRunResult:
        if shutil.which(tool_name) is None:
            return ToolRunResult(status="unavailable", payload={}, error=f"{tool_name} not found")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return ToolRunResult(status="failed", payload={}, error=f"{tool_name} timed out")

        if result.returncode not in success_codes:
            return ToolRunResult(
                status="failed",
                payload={},
                error=result.stderr.strip() or f"{tool_name} failed",
            )

        stdout = result.stdout.strip()
        if not stdout:
            return ToolRunResult(status="completed", payload={})

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return ToolRunResult(
                status="failed",
                payload={},
                error=f"{tool_name} produced non-JSON output",
            )
        return ToolRunResult(status="completed", payload=payload)
