"""Phase 0 smoke tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from repoclinic import __version__, app


def test_package_imports() -> None:
    """Ensure the package imports with expected metadata."""
    assert __version__


def test_cli_help_runs() -> None:
    """Ensure CLI wiring is operational."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "RepoClinic" in result.stdout


def test_root_main_py_help_runs() -> None:
    """Root main.py shim should expose the CLI entrypoint."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "RepoClinic" in result.stdout
