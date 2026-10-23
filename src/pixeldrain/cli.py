from __future__ import annotations

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

from pixeldrain.client import PixelDrainClient
from pixeldrain.config import Config, format_size, setup_logging
from telegram.reporter import create_reporter

console = Console()

click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: int) -> None:
    """Pixeldrain CLI: Upload, download, check, and manage Pixeldrain files."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.argument("target")
@click.option("-o", "--output", help="Destination file path.")
@click.option("-k", "--key", help="Pixeldrain API key.")
@click.option(
    "-c",
    "--concurrency",
    type=int,
    default=None,
    help="Number of concurrent chunk workers.",
)
@click.option(
    "--verify/--no-verify",
    default=True,
    help="Verify SHA256 checksum against Pixeldrain metadata.",
)
@click.option(
    "-n",
    "--notify/--no-notify",
    default=None,
    help="Stream progress and send completion alert to Telegram (default: auto if configured).",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def download(
    ctx: click.Context,
    target: str,
    output: str | None,
    key: str | None,
    concurrency: int | None,
    verify: bool,
    notify: bool,
    verbose: int,
) -> None:
    """Download a file from Pixeldrain with parallel chunks and SHA256 verification."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    reporter = create_reporter(
        title=f"Pixeldrain: {target}", target_name="Pixeldrain", enabled=notify
    )
    cb = (lambda delta, tot: reporter.advance(delta, tot)) if reporter else None
    try:
        client = PixelDrainClient(api_key=key, concurrency=concurrency, console=console)
        dest = client.download(
            target=target,
            output_path=output,
            concurrency=concurrency,
            verify_checksum=verify,
            progress_callback=cb,
        )
        if reporter:
            reporter.finish(success_url=f"Downloaded {dest.name}")
        console.print(f"[bold green][OK] Downloaded to:[/bold green] {dest.resolve()}")
    except KeyboardInterrupt:
        if reporter:
            reporter.finish(error="Cancelled by user")
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        if reporter:
            reporter.finish(error=str(e))
        console.print(f"[bold red][ERROR] Download:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("-k", "--key", help="Pixeldrain API key.")
@click.option(
    "-n",
    "--notify/--no-notify",
    default=None,
    help="Stream progress and send completion alert to Telegram (default: auto if configured).",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def upload(
    ctx: click.Context,
    file: Path,
    key: str | None,
    notify: bool,
    verbose: int,
) -> None:
    """Upload a file to Pixeldrain."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    reporter = create_reporter(
        title=f"Pixeldrain: {file.name}", target_name="Pixeldrain", enabled=notify
    )
    try:
        client = PixelDrainClient(api_key=key, console=console)
        res = client.upload(file_path=file)
        if reporter:
            reporter.finish(success_url=res.url)
        console.print(
            f"[bold green]Share URL:[/bold green] [link={res.url}]{res.url}[/link]"
        )
        console.print(f"[dim]File ID: {res.id} ({format_size(res.size)})[/dim]")
    except KeyboardInterrupt:
        if reporter:
            reporter.finish(error="Cancelled by user")
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        if reporter:
            reporter.finish(error=str(e))
        console.print(f"[bold red][ERROR] Upload:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.option("-k", "--key", help="Pixeldrain API key.")
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def info(
    ctx: click.Context,
    target: str,
    key: str | None,
    verbose: int,
) -> None:
    """Display metadata for a Pixeldrain file."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = PixelDrainClient(api_key=key, console=console)
        item = client.info(target=target)
        if not item:
            console.print(
                f"[bold red]File '{target}' not found on Pixeldrain.[/bold red]"
            )
            sys.exit(1)

        table = Table(title="Pixeldrain File Details")
        table.add_column("Property", style="bold cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", item.name)
        table.add_row("Size", format_size(item.size))
        table.add_row("ID", item.id)
        table.add_row("MIME Type", item.mime_type)
        table.add_row("SHA256", item.sha256_hash or "-")
        table.add_row("Views", str(item.views))
        table.add_row("Downloads", str(item.downloads))
        table.add_row("URL", item.url or f"https://pixeldrain.com/u/{item.id}")

        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red][ERROR] Info:[/bold red] {e}")
        sys.exit(1)


@cli.command(name="list")
@click.argument("list_id")
@click.option("-k", "--key", help="Pixeldrain API key.")
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def list_cmd(
    ctx: click.Context,
    list_id: str,
    key: str | None,
    verbose: int,
) -> None:
    """List files in a Pixeldrain list/album."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = PixelDrainClient(api_key=key, console=console)
        items = client.list(list_id=list_id)

        if not items:
            console.print("[yellow]No files found in list.[/yellow]")
            return

        table = Table(title=f"Pixeldrain List: {list_id}")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Size", justify="right", style="green")
        table.add_column("SHA256", style="dim")

        for item in items:
            table.add_row(
                item.id, item.name, format_size(item.size), item.sha256_hash or "-"
            )

        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red][ERROR] List:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.option("-k", "--key", help="Pixeldrain API key.")
@click.option("-f", "--force", is_flag=True, help="Confirm deletion without prompting.")
def delete(
    target: str,
    key: str | None,
    force: bool,
) -> None:
    """Delete a file from Pixeldrain."""
    if not force:
        from rich.prompt import Confirm

        if not Confirm.ask(
            f"[yellow]Are you sure you want to delete file '{target}'?[/yellow]"
        ):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        client = PixelDrainClient(api_key=key, console=console)
        ok = client.delete(target=target)
        if ok:
            console.print(
                f"[bold green][OK] File '{target}' deleted successfully.[/bold green]"
            )
        else:
            console.print(f"[bold red]Failed to delete '{target}'.[/bold red]")
            sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red][ERROR] Delete:[/bold red] {e}")
        sys.exit(1)


@cli.group()
def config() -> None:
    """Manage local Pixeldrain CLI configuration profile."""


@config.command(name="show")
def config_show() -> None:
    """Show current configuration settings."""
    cfg = Config.load()
    table = Table(title="Pixeldrain Local Configuration")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="yellow")

    table.add_row("API Key", cfg.api_key or "[dim](not set)[/dim]")
    table.add_row("Concurrency", str(cfg.concurrency))
    table.add_row("Chunk Size", format_size(cfg.chunk_size))
    console.print(table)


@config.command(name="set")
@click.option("-k", "--key", help="Default Pixeldrain API key.")
@click.option("-c", "--concurrency", type=int, help="Default download concurrency.")
def config_set(
    key: str | None,
    concurrency: int | None,
) -> None:
    """Update and persist default settings to config.toml."""
    try:
        cfg = Config.load()
        if key is not None:
            cfg.api_key = key
        if concurrency is not None:
            cfg.concurrency = concurrency

        cfg.save()
        console.print("[bold green][OK] Configuration saved.[/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
