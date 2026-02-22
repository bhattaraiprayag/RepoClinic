"""RepoClinic package entrypoints."""

from repoclinic.cli import app
from repoclinic.constants import PACKAGE_VERSION

__all__ = ["app", "main", "__version__"]
__version__ = PACKAGE_VERSION


def main() -> None:
    """Launch the CLI."""
    app()
