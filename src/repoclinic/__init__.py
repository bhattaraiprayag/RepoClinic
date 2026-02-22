"""RepoClinic package entrypoints."""

from repoclinic.cli import app
from repoclinic.constants import PACKAGE_VERSION
from repoclinic.runtime_env import load_runtime_env

__all__ = ["app", "main", "__version__"]
__version__ = PACKAGE_VERSION


def main() -> None:
    """Launch the CLI."""
    load_runtime_env()
    app()
