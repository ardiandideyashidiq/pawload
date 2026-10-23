from __future__ import annotations

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

from telegram.reporter import create_reporter
from vikingfile.client import VikingFileClient
from vikingfile.config import Config, format_size, setup_logging

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
    """VikingFile CLI: Upload, check, download, and manage Vikingfile files."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("-u", "--user", help="User account hash (leave empty for anonymous).")
@click.option(
    "-d", "--remote-dir", default="", help="Destination folder path on VikingFile."
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
def upload(
    ctx: click.Context,
    file: Path,
    user: str | None,
    remote_dir: str,
    notify: bool,
    verbose: int,
) -> None:
    """Upload a file to VikingFile anonymously or to your user account."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    reporter = create_reporter(
        title=f"VikingFile: {file.name}", target_name="VikingFile", enabled=notify
    )
    try:
        client = VikingFileClient(user=user, console=console)
        result = client.upload(file_path=file, remote_path=remote_dir)
        if reporter:
            reporter.finish(success_url=result.url)
        console.print(
            f"[bold green]Share URL:[/bold green] [link={result.url}]{result.url}[/link]"
        )
        console.print(
            f"[dim]File Hash: {result.hash} ({format_size(result.size)})[/dim]"
        )
    except KeyboardInterrupt:
        if reporter:
            reporter.finish(error="Cancelled by user")
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        if reporter:
            reporter.finish(error=str(e))
        console.print(f"[bold red]Upload Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def check(ctx: click.Context, target: str, verbose: int) -> None:
    """Check if a file exists on VikingFile and display metadata."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = VikingFileClient(console=console)
        info = client.check(target=target)
        if not info or not info.exist:
            console.print(
                f"[bold red]File '{target}' not found or deleted on VikingFile.[/bold red]"
            )
            sys.exit(1)

        table = Table(title="VikingFile Details")
        table.add_column("Property", style="bold cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", info.name)
        table.add_row("Size", format_size(info.size))
        table.add_row("Hash", info.hash)
        table.add_row("URL", info.url or f"https://vikingfile.com/f/{info.hash}")
        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Check Error:[/bold red] {e}")
        sys.exit(1)


@cli.command(name="list")
@click.option("-u", "--user", help="User account hash.")
@click.option("-p", "--page", default=1, type=int, help="Page number.")
@click.option("-d", "--remote-dir", default="", help="Subfolder path.")
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
    user: str | None,
    page: int,
    remote_dir: str,
    verbose: int,
) -> None:
    """List files in your VikingFile account."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = VikingFileClient(user=user, console=console)
        items = client.list(page=page, remote_path=remote_dir)

        if not items:
            console.print("[yellow]No files found.[/yellow]")
            return

        table = Table(title=f"VikingFile User Files (Page {page})")
        table.add_column("Hash", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Downloads", justify="right", style="magenta")

        for item in items:
            table.add_row(
                item.hash, item.name, format_size(item.size), str(item.downloads)
            )

        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]List Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.option("-u", "--user", help="User account hash.")
@click.option("-f", "--force", is_flag=True, help="Confirm deletion without prompting.")
def delete(
    target: str,
    user: str | None,
    force: bool,
) -> None:
    """Delete a file from your VikingFile account."""
    if not force:
        from rich.prompt import Confirm

        if not Confirm.ask(
            f"[yellow]Are you sure you want to delete file '{target}'?[/yellow]"
        ):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        client = VikingFileClient(user=user, console=console)
        ok = client.delete(target=target)
        if ok:
            console.print(
                f"[bold green]✓ File '{target}' deleted successfully.[/bold green]"
            )
        else:
            console.print(
                f"[bold red]Failed to delete '{target}'. Verify user hash and file hash.[/bold red]"
            )
            sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Delete Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.argument("new_name")
@click.option("-u", "--user", help="User account hash.")
def rename(
    target: str,
    new_name: str,
    user: str | None,
) -> None:
    """Rename a file in your VikingFile account."""
    try:
        client = VikingFileClient(user=user, console=console)
        ok = client.rename(target=target, new_filename=new_name)
        if ok:
            console.print(
                f"[bold green]✓ Renamed '{target}' to '{new_name}'.[/bold green]"
            )
        else:
            console.print(f"[bold red]Failed to rename '{target}'.[/bold red]")
            sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Rename Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.option("-o", "--output", help="Destination file path.")
@click.option(
    "-c", "--concurrency", type=int, default=None, help="Parallel chunk workers."
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
    concurrency: int | None,
    notify: bool,
    verbose: int,
) -> None:
    """Download a direct file URL with parallel chunks and resume support."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    reporter = create_reporter(
        title=f"VikingFile: {target}", target_name="VikingFile", enabled=notify
    )
    cb = (lambda delta, tot: reporter.advance(delta, tot)) if reporter else None
    try:
        client = VikingFileClient(console=console)
        dest = client.download(
            target=target,
            output_path=output,
            concurrency=concurrency,
            progress_callback=cb,
        )
        if reporter:
            reporter.finish(success_url=f"Downloaded {dest.name}")
        console.print(f"[bold green]✓ Downloaded to:[/bold green] {dest.resolve()}")
    except KeyboardInterrupt:
        if reporter:
            reporter.finish(error="Cancelled by user")
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        if reporter:
            reporter.finish(error=str(e))
        console.print(f"[bold red]Download Error:[/bold red] {e}")
        sys.exit(1)


@cli.group()
def config() -> None:
    """Manage local VikingFile CLI configuration profile."""


@config.command(name="show")
def config_show() -> None:
    """Show current configuration settings."""
    cfg = Config.load()
    table = Table(title="VikingFile Local Configuration")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="yellow")

    table.add_row("User Hash", cfg.user or "[dim](not set, anonymous uploads)[/dim]")
    table.add_row("Concurrency", str(cfg.concurrency))
    table.add_row("Chunk Size", format_size(cfg.chunk_size))
    console.print(table)


@config.command(name="set")
@click.option("-u", "--user", help="Default user account hash.")
@click.option("-c", "--concurrency", type=int, help="Default download concurrency.")
def config_set(
    user: str | None,
    concurrency: int | None,
) -> None:
    """Update and persist default settings to config.toml."""
    try:
        cfg = Config.load()
        if user is not None:
            cfg.user = user
        if concurrency is not None:
            cfg.concurrency = concurrency

        cfg.save()
        console.print("[bold green]✓ Configuration saved.[/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
