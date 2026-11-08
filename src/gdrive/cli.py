from __future__ import annotations

import sys

import rich_click as click
from rich.console import Console
from rich.table import Table

from gdrive.client import GDriveClient
from gdrive.config import Config, format_size, setup_logging
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
    """Google Drive CLI: Inspect, resolve direct download links, and download files."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.argument("target")
@click.option(
    "-k",
    "--cookies",
    "--cookie",
    "--cookie-file",
    "cookies",
    default=None,
    help="Netscape cookies.txt file path or raw cookie string ('SID=...; HSID=...').",
)
def info(target: str, cookies: str | None) -> None:
    """Inspect a Google Drive link or ID (file or folder)."""
    try:
        client = GDriveClient(cookies=cookies, console=console)
        item = client.info(target)

        table = Table(title="Google Drive Item Details")
        table.add_column("Property", style="bold cyan")
        table.add_column("Value", style="yellow")

        table.add_row("ID", item.id)
        table.add_row("Name", item.name)
        table.add_row("Type", "Folder" if item.is_folder else "File")
        if not item.is_folder:
            table.add_row("Size", format_size(item.size))
            if item.direct_url:
                table.add_row("Direct URL", item.direct_url)
        else:
            table.add_row("Files Count", str(len(item.children)))

        console.print(table)

        if item.is_folder and item.children:
            subtable = Table(title=f"Files in folder '{item.name}'")
            subtable.add_column("ID", style="cyan")
            subtable.add_column("Name", style="bold")
            subtable.add_column("Size", justify="right", style="green")
            subtable.add_column("MIME", style="dim")

            for child in item.children:
                subtable.add_row(child.id, child.name, format_size(child.size), child.mime_type)
            console.print(subtable)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red][ERROR] Info:[/bold red] {e}")
        sys.exit(1)


@cli.command(name="url")
@click.argument("target")
@click.option(
    "-k",
    "--cookies",
    "--cookie",
    "--cookie-file",
    "cookies",
    default=None,
    help="Netscape cookies.txt file path or raw cookie string ('SID=...; HSID=...').",
)
def direct_url_cmd(target: str, cookies: str | None) -> None:
    """Scrape and resolve the direct download URL for a file or folder."""
    try:
        client = GDriveClient(cookies=cookies, console=console)
        with console.status("[bold green]Resolving direct download link...[/bold green]"):
            url, filename, total_size = client.get_direct_url(target)

        table = Table(title="Google Drive Direct Download")
        table.add_column("Property", style="bold cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Filename", filename)
        table.add_row("Total Size", format_size(total_size))
        table.add_row("Direct URL", url)

        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red][ERROR] Direct URL:[/bold red] {e}")
        sys.exit(1)


@cli.command(name="list")
@click.argument("target")
@click.option(
    "-k",
    "--cookies",
    "--cookie",
    "--cookie-file",
    "cookies",
    default=None,
    help="Netscape cookies.txt file path or raw cookie string ('SID=...; HSID=...').",
)
def list_cmd(target: str, cookies: str | None) -> None:
    """List files in a Google Drive folder."""
    try:
        client = GDriveClient(cookies=cookies, console=console)
        items = client.list(target)

        if not items:
            console.print("[yellow]No files found in folder.[/yellow]")
            return

        table = Table(title="Google Drive Folder Contents")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Type", style="dim")

        for item in items:
            table.add_row(
                item.id,
                item.name,
                format_size(item.size),
                "Folder" if item.is_folder else (item.mime_type or "File"),
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
@click.option("-o", "--output", help="Destination file path or directory.")
@click.option("-c", "--concurrency", type=int, default=None, help="Parallel chunk workers.")
@click.option(
    "-k",
    "--cookies",
    "--cookie",
    "--cookie-file",
    "cookies",
    default=None,
    help="Netscape cookies.txt file path or raw cookie string ('SID=...; HSID=...').",
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
    cookies: str | None,
    notify: bool,
    verbose: int,
) -> None:
    """Download a Google Drive file with parallel chunk workers and resume support."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    reporter = create_reporter(
        title=f"GDrive: {target}", target_name="GDrive", enabled=notify
    )
    cb = (lambda delta, tot: reporter.advance(delta, tot)) if reporter else None
    try:
        client = GDriveClient(cookies=cookies, concurrency=concurrency, console=console)
        dest = client.download(
            target=target,
            output_path=output,
            concurrency=concurrency,
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


@cli.group()
def config() -> None:
    """Manage local Google Drive CLI configuration profile."""


@config.command(name="show")
def config_show() -> None:
    """Show current configuration settings."""
    cfg = Config.load()
    table = Table(title="Google Drive Configuration")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Cookie File", cfg.cookie_file or "[dim](not set)[/dim]")
    table.add_row("Concurrency", str(cfg.concurrency))
    table.add_row("Chunk Size", format_size(cfg.chunk_size))
    console.print(table)


@config.command(name="set")
@click.option("-k", "--cookie-file", help="Path to Netscape cookies.txt file.")
@click.option("-c", "--concurrency", type=int, help="Default download concurrency.")
def config_set(cookie_file: str | None, concurrency: int | None) -> None:
    """Update and persist settings to config.toml."""
    try:
        cfg = Config.load()
        if cookie_file is not None:
            cfg.cookie_file = cookie_file
        if concurrency is not None:
            cfg.concurrency = concurrency

        cfg.save()
        console.print("[bold green][OK] Configuration saved.[/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red][ERROR] Config Set:[/bold red] {e}")
        sys.exit(1)
