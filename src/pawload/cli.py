from __future__ import annotations

import rich_click as click
from rich.console import Console
from rich.table import Table

import sourceforge.config as sf_cfg
from gofile.cli import cli as gofile_cli
from pixeldrain.cli import cli as pixeldrain_cli
from sourceforge.cli import cli as sourceforge_cli
from telegram.cli import cli as telegram_cli
from vikingfile.cli import cli as vikingfile_cli
from web.cli import cli as web_cli

click.rich_click.USE_RICH_MARKUP = True

ALIASES: dict[str, click.Command] = {
    "gf": gofile_cli,
    "pd": pixeldrain_cli,
    "sf": sourceforge_cli,
    "vf": vikingfile_cli,
    "tg": telegram_cli,
    "gui": web_cli,
}


class PawloadGroup(click.Group):
    """Click group that supports shorthand aliases without cluttering help listings."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        return ALIASES.get(cmd_name)


@click.group(cls=PawloadGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: int) -> None:
    """Pawload: Unified multi-cloud transfer, scraping, and storage CLI."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.group(name="config")
def config_group() -> None:
    """Manage unified Pawload configuration profile."""


@config_group.command(name="path")
def config_path() -> None:
    """Print active configuration file path."""
    Console().print(str(sf_cfg.CONFIG_FILE))


@config_group.command(name="show")
def config_show() -> None:
    """Show current configuration settings for all services."""
    console = Console()
    console.print(f"[dim]Config file: {sf_cfg.CONFIG_FILE}[/dim]")
    all_sec = sf_cfg.load_all_sections(config_file=sf_cfg.CONFIG_FILE)
    if not all_sec:
        console.print(
            "[yellow]Unified configuration file is empty or not created yet.[/yellow]"
        )
        return
    for sec_name, sec_data in all_sec.items():
        table = Table(title=f"Configuration: {sec_name}", show_header=True)
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="yellow")
        if isinstance(sec_data, dict):
            for k, v in sec_data.items():
                table.add_row(k, str(v))
        else:
            table.add_row(sec_name, str(sec_data))
        console.print(table)


# Attach primary service CLIs as subcommands
cli.add_command(gofile_cli, name="gofile")
cli.add_command(pixeldrain_cli, name="pixeldrain")
cli.add_command(sourceforge_cli, name="sourceforge")
cli.add_command(vikingfile_cli, name="vikingfile")
cli.add_command(telegram_cli, name="telegram")
cli.add_command(web_cli, name="web")
