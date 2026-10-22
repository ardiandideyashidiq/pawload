from __future__ import annotations

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

from gofile.client import GoFileClient
from gofile.config import Config, format_size, setup_logging

console = Console()

click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", count=True, default=0, help="Enable verbose logging (-v for INFO, -vv for DEBUG).")
@click.pass_context
def cli(ctx: click.Context, verbose: int) -> None:
    """GoFile CLI: Upload, download, and manage GoFile.io files."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.argument("target")
@click.option("-o", "--output", help="Destination file or directory path.")
@click.option("-p", "--password", help="Password for protected folders/files.")
@click.option("-t", "--token", help="GoFile account token (uses guest account if omitted).")
@click.option("-c", "--concurrency", type=int, default=None, help="Number of concurrent chunk workers.")
@click.option("--all", "download_all", is_flag=True, help="Download all files in the folder.")
@click.option("--verify/--no-verify", default=True, help="Verify MD5 checksum against GoFile metadata.")
@click.option("-v", "--verbose", count=True, default=0, help="Enable verbose logging (-v for INFO, -vv for DEBUG).")
@click.pass_context
def download(
    ctx: click.Context,
    target: str,
    output: str | None,
    password: str | None,
    token: str | None,
    concurrency: int | None,
    download_all: bool,
    verify: bool,
    verbose: int,
) -> None:
    """Download a file or folder from GoFile with parallel chunks and resume support."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = GoFileClient(token=token, concurrency=concurrency, console=console)
        dest = client.download(
            target=target,
            output_path=output,
            password=password,
            concurrency=concurrency,
            verify_checksum=verify,
            interactive=True,
            download_all=download_all,
        )
        if isinstance(dest, list):
            console.print(f"[bold green]✓ Downloaded {len(dest)} files to:[/bold green] {output or target}")
        else:
            console.print(f"[bold green]✓ Downloaded to:[/bold green] {dest.resolve()}")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Download Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("-f", "--folder-id", help="Destination folder ID on GoFile.")
@click.option("-t", "--token", help="GoFile account token.")
@click.option("-v", "--verbose", count=True, default=0, help="Enable verbose logging (-v for INFO, -vv for DEBUG).")
@click.pass_context
def upload(
    ctx: click.Context,
    file: Path,
    folder_id: str | None,
    token: str | None,
    verbose: int,
) -> None:
    """Upload a file to GoFile with real-time streaming progress."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = GoFileClient(token=token, console=console)
        result = client.upload(file_path=file, folder_id=folder_id)
        console.print(f"[bold green]Download Page:[/bold green] [link={result.download_page}]{result.download_page}[/link]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Upload Error:[/bold red] {e}")
        sys.exit(1)


@cli.command(name="list")
@click.argument("target")
@click.option("-p", "--password", help="Password for protected folders/files.")
@click.option("-t", "--token", help="GoFile account token.")
@click.option("-v", "--verbose", count=True, default=0, help="Enable verbose logging (-v for INFO, -vv for DEBUG).")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    target: str,
    password: str | None,
    token: str | None,
    verbose: int,
) -> None:
    """List contents of a GoFile folder or file URL."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = GoFileClient(token=token, console=console)
        items = client.list(target=target, password=password)

        if not items:
            console.print("[yellow]No files or folders found.[/yellow]")
            return

        table = Table(title=f"GoFile Contents: {target}")
        table.add_column("Type", justify="center", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified (UTC)", style="dim")
        table.add_column("MD5 Hash", style="magenta")

        for item in items:
            item_type = "[blue]DIR[/blue]" if item.is_dir else "[white]FILE[/white]"
            size_str = "-" if item.is_dir else format_size(item.size)
            mtime_str = item.modified_time.strftime("%Y-%m-%d %H:%M:%S") if item.modified_time else "-"
            md5_str = item.md5 or "-"
            table.add_row(item_type, item.name, size_str, mtime_str, md5_str)

        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]List Error:[/bold red] {e}")
        sys.exit(1)


@cli.group()
def config() -> None:
    """Manage local GoFile CLI configuration profile."""


@config.command(name="show")
def config_show() -> None:
    """Show current configuration settings."""
    cfg = Config.load()
    table = Table(title="GoFile Local Configuration")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Token", cfg.token or "[dim](not set, auto-guest)[/dim]")
    table.add_row("Account ID", cfg.account_id or "[dim](not set)[/dim]")
    table.add_row("Root Folder", cfg.root_folder or "[dim](not set)[/dim]")
    table.add_row("Concurrency", str(cfg.concurrency))
    table.add_row("Chunk Size", format_size(cfg.chunk_size))
    console.print(table)


@config.command(name="set")
@click.option("-t", "--token", help="GoFile account token.")
@click.option("-c", "--concurrency", type=int, help="Default download concurrency.")
def config_set(
    token: str | None,
    concurrency: int | None,
) -> None:
    """Update and persist default settings to config.toml."""
    try:
        cfg = Config.load()
        if token is not None:
            cfg.token = token
        if concurrency is not None:
            cfg.concurrency = concurrency

        cfg.save()
        console.print("[bold green]✓ Configuration saved.[/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
