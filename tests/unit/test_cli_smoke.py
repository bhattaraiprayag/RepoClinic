"""Phase 0 smoke tests."""

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
