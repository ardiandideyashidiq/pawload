from __future__ import annotations

import sys

import rich_click as click
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

import gofile.config as gf_cfg
import pixeldrain.config as pd_cfg
import sourceforge.config as sf_cfg
import telegram.config as tg_cfg
import vikingfile.config as vf_cfg
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


def run_interactive_setup(console: Console) -> None:
    """Interactively walk through each provider/service configuration."""
    console.print("\n[bold cyan]=== Pawload Interactive Configuration Setup ===[/bold cyan]")
    console.print(f"[dim]Target config file: {sf_cfg.CONFIG_FILE}[/dim]\n")

    # 1. Global settings
    if Confirm.ask("[bold]Configure global settings (concurrency)?[/bold]", default=True):
        current_sections = sf_cfg.load_all_sections(config_file=sf_cfg.CONFIG_FILE)
        global_sec = current_sections.get("global", {})
        default_conc = str(global_sec.get("concurrency", 4))
        conc_val = Prompt.ask("Default download concurrency", default=default_conc)
        try:
            sf_cfg.save_section("global", {"concurrency": int(conc_val)}, config_file=sf_cfg.CONFIG_FILE)
            console.print("[green][ok] Saved [global][/green]\n")
        except ValueError:
            console.print("[yellow]Invalid integer, skipping global concurrency.[/yellow]\n")

    # 2. SourceForge
    if Confirm.ask("[bold]Configure SourceForge?[/bold]", default=True):
        sf_c = sf_cfg.Config.load()
        user = Prompt.ask("SourceForge username", default=sf_c.username or "")
        proj = Prompt.ask("SourceForge default project", default=sf_c.project or "")
        key = Prompt.ask("SSH private key path", default=sf_c.key_path or "")
        mirror = Prompt.ask("Default mirror ID (e.g. autoselect, master)", default=sf_c.default_mirror or "autoselect")
        sf_c.username = user.strip() or None
        sf_c.project = proj.strip() or None
        sf_c.key_path = key.strip() or None
        sf_c.default_mirror = mirror.strip() or None
        sf_c.save()
        console.print("[green][ok] Saved [sourceforge][/green]\n")

    # 3. GoFile
    if Confirm.ask("[bold]Configure GoFile?[/bold]", default=True):
        gf_c = gf_cfg.Config.load()
        token = Prompt.ask("GoFile account token (leave blank for guest)", default=gf_c.token or "")
        gf_c.token = token.strip() or None
        gf_c.save()
        console.print("[green][ok] Saved [gofile][/green]\n")

    # 4. Pixeldrain
    if Confirm.ask("[bold]Configure Pixeldrain?[/bold]", default=True):
        pd_c = pd_cfg.Config.load()
        api_key = Prompt.ask("Pixeldrain API key (leave blank for anonymous)", default=pd_c.api_key or "")
        pd_c.api_key = api_key.strip() or None
        pd_c.save()
        console.print("[green][ok] Saved [pixeldrain][/green]\n")

    # 5. VikingFile
    if Confirm.ask("[bold]Configure VikingFile?[/bold]", default=True):
        vf_c = vf_cfg.Config.load()
        user_hash = Prompt.ask("VikingFile user account hash (leave blank for anonymous)", default=vf_c.user or "")
        vf_c.user = user_hash.strip()
        vf_c.save()
        console.print("[green][ok] Saved [vikingfile][/green]\n")

    # 6. Telegram Notifications
    if Confirm.ask("[bold]Configure Telegram Bot & Notifications?[/bold]", default=False):
        tg_c = tg_cfg.Config.load()
        bot_tok = Prompt.ask("Telegram bot token", default=tg_c.bot_token or "")
        chat_id = Prompt.ask("Default chat ID or channel", default=tg_c.chat_id or "")
        thread_id_val = Prompt.ask("Topic thread ID (optional)", default=str(tg_c.thread_id or ""))
        tg_c.bot_token = bot_tok.strip() or None
        tg_c.chat_id = chat_id.strip() or None
        if thread_id_val.strip().isdigit():
            tg_c.thread_id = int(thread_id_val.strip())
        tg_c.save()
        console.print("[green][ok] Saved [telegram][/green]\n")

    console.print("[bold green]All configuration saved successfully![/bold green]")
    console.print("Inspect settings anytime using: [cyan]pawload config show[/cyan]\n")


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


@cli.command(name="setup")
def setup_cmd() -> None:
    """Interactively configure credentials and defaults for each service."""
    console = Console()
    try:
        run_interactive_setup(console)
    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled by user.[/yellow]")
        sys.exit(130)


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
