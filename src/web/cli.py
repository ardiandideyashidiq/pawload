from __future__ import annotations

import rich_click as click
from loguru import logger

from sourceforge.config import setup_logging
from web.app import run_server


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Increase verbosity (-v for INFO, -vv for DEBUG).",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host interface to bind server (default: 0.0.0.0).",
)
@click.option(
    "--port",
    type=int,
    default=8765,
    help="Port to bind server (default: 8765).",
)
@click.option(
    "--open-browser/--no-browser",
    default=True,
    help="Automatically open web browser.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: int,
    host: str,
    port: int,
    open_browser: bool,
) -> None:
    """MultiCloud Web App (Flask + Tailwind CSS + shadcn components)."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)

    if ctx.invoked_subcommand is None:
        run_server(host=host, port=port, open_browser=open_browser)


@cli.command("serve")
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host interface to bind server (default: 0.0.0.0).",
)
@click.option(
    "--port",
    type=int,
    default=8765,
    help="Port to bind server (default: 8765).",
)
@click.option(
    "--open-browser/--no-browser",
    default=True,
    help="Automatically open web browser.",
)
def serve_command(host: str, port: int, open_browser: bool) -> None:
    """Launch the Flask web transfer dashboard."""
    run_server(host=host, port=port, open_browser=open_browser)


def main() -> None:
    try:
        cli()
    except Exception as e:
        logger.error(f"Fatal error in web server: {e}")
