"""CLI for RepoClinic."""

import typer

from repoclinic.constants import PACKAGE_VERSION

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="RepoClinic deterministic repository analysis pipeline.",
)


@app.command()
def version() -> None:
    """Print the RepoClinic version."""
    typer.echo(PACKAGE_VERSION)
