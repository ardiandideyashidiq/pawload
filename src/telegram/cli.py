from __future__ import annotations

import sys

import rich_click as click
from rich.console import Console
from rich.table import Table

from telegram.client import TelegramClient
from telegram.config import Config, setup_logging

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Increase verbosity (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: int) -> None:
    """Telegram notifications, progress streaming, and bot runner."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command("send")
@click.argument("text")
@click.option(
    "--chat-id",
    "-c",
    default=None,
    help="Target chat ID or @channel (defaults to config).",
)
@click.option(
    "--thread-id", "-t", type=int, default=None, help="Target topic thread ID."
)
@click.option("-v", "--verbose", count=True, default=0, help="Increase verbosity.")
@click.pass_context
def send_cmd(
    ctx: click.Context,
    text: str,
    chat_id: str | None,
    thread_id: int | None,
    verbose: int,
) -> None:
    """Send a notification message to Telegram."""
    lvl = max(ctx.obj.get("verbose", 0), verbose)
    setup_logging(lvl)
    try:
        client = TelegramClient(chat_id=chat_id, thread_id=thread_id)
        msg = client.send_message(text=text)
        console.print(
            f"[green][OK] Message sent successfully[/green] (ID: {msg.get('message_id')})"
        )
    except Exception as e:
        console.print(f"[bold red][ERROR] Send:[/bold red] {e}")
        sys.exit(1)


@cli.command("test")
@click.option("-v", "--verbose", count=True, default=0, help="Increase verbosity.")
@click.pass_context
def test_cmd(ctx: click.Context, verbose: int) -> None:
    """Verify Telegram bot credentials and test chat connectivity."""
    lvl = max(ctx.obj.get("verbose", 0), verbose)
    setup_logging(lvl)
    try:
        client = TelegramClient()
        console.print("[cyan]Testing bot authentication (getMe)...[/cyan]")
        bot_info = client.get_me()
        console.print(
            f"[green][OK] Authenticated as:[/green] @{bot_info.get('username')} ({bot_info.get('first_name')})"
        )

        if client.chat_id:
            console.print(f"[cyan]Sending ping to chat {client.chat_id}...[/cyan]")
            msg = client.send_message(
                "[PING] <b>Ping:</b> Telegram bot connectivity verified!", parse_mode="HTML"
            )
            console.print(
                f"[green][OK] Ping sent successfully[/green] (ID: {msg.get('message_id')})"
            )
        else:
            console.print(
                "[yellow]Notice: No chat_id configured. To test sending messages, configure TELEGRAM_CHAT_ID.[/yellow]"
            )
    except Exception as e:
        console.print(f"[bold red][ERROR] Test:[/bold red] {e}")
        sys.exit(1)


@cli.command("bot")
@click.option("--token", default=None, help="Bot token override.")
@click.option("-v", "--verbose", count=True, default=0, help="Increase verbosity.")
@click.pass_context
def bot_cmd(ctx: click.Context, token: str | None, verbose: int) -> None:
    """Start interactive long-polling bot daemon."""
    lvl = max(ctx.obj.get("verbose", 0), verbose)
    setup_logging(lvl)
    from telegram.bot import run_bot

    try:
        run_bot(bot_token=token)
    except KeyboardInterrupt:
        console.print("\n[yellow]Bot daemon stopped by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red][ERROR] Bot:[/bold red] {e}")
        sys.exit(1)


@cli.group("config")
def config_group() -> None:
    """Manage Telegram configuration."""


@config_group.command("show")
def config_show() -> None:
    """Show current Telegram settings."""
    cfg = Config.load()
    table = Table(title="Telegram Configuration", show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")

    token_display = (
        f"{cfg.bot_token[:6]}...{cfg.bot_token[-4:]}"
        if cfg.bot_token and len(cfg.bot_token) > 10
        else (cfg.bot_token or "(not set)")
    )
    table.add_row("bot_token", token_display)
    table.add_row("chat_id", cfg.chat_id or "(not set)")
    table.add_row(
        "thread_id", str(cfg.thread_id) if cfg.thread_id is not None else "(not set)"
    )
    table.add_row("throttle_interval", f"{cfg.throttle_interval}s")
    table.add_row("parse_mode", cfg.parse_mode)

    console.print(table)


@config_group.command("set")
@click.option("--token", default=None, help="Telegram bot token.")
@click.option("--chat-id", default=None, help="Default chat ID or channel username.")
@click.option("--thread-id", type=int, default=None, help="Default topic thread ID.")
@click.option(
    "--throttle",
    type=float,
    default=None,
    help="Throttle interval in seconds (default: 2.0).",
)
def config_set(
    token: str | None,
    chat_id: str | None,
    thread_id: int | None,
    throttle: float | None,
) -> None:
    """Update Telegram settings."""
    cfg = Config.load()
    if token is not None:
        cfg.bot_token = token
    if chat_id is not None:
        cfg.chat_id = chat_id
    if thread_id is not None:
        cfg.thread_id = thread_id
    if throttle is not None:
        cfg.throttle_interval = throttle

    cfg.save()
    console.print("[green][OK] Configuration saved.[/green]")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
