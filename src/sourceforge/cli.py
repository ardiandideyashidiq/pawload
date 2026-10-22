from __future__ import annotations

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

from sourceforge.client import SourceForgeClient
from sourceforge.config import Config
from sourceforge.mirrors import prompt_mirror

console = Console()

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True


def format_size(bytes_val: int) -> str:
    if bytes_val <= 0:
        return "0 B"
    val = float(bytes_val)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.1f} PB"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """SourceForge CLI: Upload, download, and manage FRS releases."""


@cli.command()
@click.argument("remote_path")
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-o", "--output", help="Destination file or directory path.")
@click.option("-m", "--mirror", help="Mirror ID (e.g., cfhcable, delska, twds, master, autoselect).")
@click.option("-c", "--concurrency", type=int, default=None, help="Number of concurrent chunk workers.")
@click.option("--verify/--no-verify", default=True, help="Verify MD5 checksum against SourceForge metadata.")
@click.option("--prompt/--no-prompt", default=True, help="Interactively prompt for mirror region if not set.")
def download(
    remote_path: str,
    project: str | None,
    output: str | None,
    mirror: str | None,
    concurrency: int | None,
    verify: bool,
    prompt: bool,
) -> None:
    """Download a file with parallel chunks, resume support, and checksum verification."""
    try:
        client = SourceForgeClient(project=project, console=console)
        dest = client.download(
            remote_path=remote_path,
            output_path=output,
            mirror=mirror,
            concurrency=concurrency,
            verify_checksum=verify,
            interactive_prompt=prompt,
        )
        console.print(f"[bold green]✓ Downloaded to:[/bold green] {dest.resolve()}")
    except Exception as e:
        console.print(f"[bold red]Download Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-d", "--remote-dir", default="", help="Remote subfolder within project.")
@click.option("-u", "--username", help="SourceForge username.")
@click.option("-k", "--key", help="Path to SSH private key.")
@click.option("-f", "--force", is_flag=True, help="Overwrite remote file if it already exists.")
def upload(
    file: Path,
    project: str | None,
    remote_dir: str,
    username: str | None,
    key: str | None,
    force: bool,
) -> None:
    """Upload a file via SFTP with automatic directory creation and resume support."""
    try:
        client = SourceForgeClient(project=project, username=username, key_path=key, console=console)
        remote_target = client.upload(
            local_path=file,
            remote_dir=remote_dir,
            force=force,
            interactive=True,
        )
        console.print(f"[bold green]✓ Upload complete:[/bold green] {remote_target}")
    except Exception as e:
        console.print(f"[bold red]Upload Error:[/bold red] {e}")
        sys.exit(1)


@cli.command(name="list")
@click.argument("remote_dir", default="", required=False)
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-u", "--username", help="SourceForge username (uses SFTP if provided).")
@click.option("--rss", is_flag=True, help="Force unauthenticated public RSS feed listing.")
@click.option("--sftp", is_flag=True, help="Force SFTP real-time filesystem listing.")
def list_cmd(
    remote_dir: str,
    project: str | None,
    username: str | None,
    rss: bool,
    sftp: bool,
) -> None:
    """List remote files and folders in project."""
    try:
        use_sftp = True if sftp else (False if rss else None)
        client = SourceForgeClient(project=project, username=username, console=console)
        items = client.list(remote_dir=remote_dir, use_sftp=use_sftp)

        if not items:
            console.print("[yellow]No files or folders found.[/yellow]")
            return

        table = Table(title=f"Files in {client.project}/{remote_dir.strip('/')}")
        table.add_column("Type", justify="center", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified (UTC)", style="magenta")
        table.add_column("MD5 Hash", style="dim")

        for item in items:
            item_type = "[blue]DIR[/blue]" if item.is_dir else "[white]FILE[/white]"
            size_str = "-" if item.is_dir else format_size(item.size)
            mtime_str = item.modified_time.strftime("%Y-%m-%d %H:%M:%S") if item.modified_time else "-"
            md5_str = item.md5 or "-"
            table.add_row(item_type, item.name, size_str, mtime_str, md5_str)

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]List Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("remote_path")
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-u", "--username", help="SourceForge username.")
@click.option("-k", "--key", help="Path to SSH private key.")
@click.option("-f", "--force", is_flag=True, help="Confirm deletion without prompting.")
def delete(
    remote_path: str,
    project: str | None,
    username: str | None,
    key: str | None,
    force: bool,
) -> None:
    """Delete a remote file or folder via SFTP."""
    if not force:
        from rich.prompt import Confirm

        if not Confirm.ask(f"[yellow]Are you sure you want to delete remote path '{remote_path}'?[/yellow]"):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        client = SourceForgeClient(project=project, username=username, key_path=key, console=console)
        client.delete(remote_path=remote_path)
    except Exception as e:
        console.print(f"[bold red]Delete Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("old_path")
@click.argument("new_path")
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-u", "--username", help="SourceForge username.")
@click.option("-k", "--key", help="Path to SSH private key.")
def rename(
    old_path: str,
    new_path: str,
    project: str | None,
    username: str | None,
    key: str | None,
) -> None:
    """Rename or move a remote file or folder via SFTP."""
    try:
        client = SourceForgeClient(project=project, username=username, key_path=key, console=console)
        client.rename(old_remote_path=old_path, new_remote_path=new_path)
    except Exception as e:
        console.print(f"[bold red]Rename Error:[/bold red] {e}")
        sys.exit(1)


@cli.group()
def config() -> None:
    """Manage local SourceForge CLI configuration profile."""


@config.command(name="show")
def config_show() -> None:
    """Show current configuration settings."""
    cfg = Config.load()
    table = Table(title="SourceForge Local Configuration")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Username", cfg.username or "[dim](not set)[/dim]")
    table.add_row("Project", cfg.project or "[dim](not set)[/dim]")
    table.add_row("SSH Key", cfg.key_path or "[dim](not set)[/dim]")
    table.add_row("Default Mirror", cfg.default_mirror or "[dim](not set)[/dim]")
    table.add_row("Concurrency", str(cfg.concurrency))
    table.add_row("Chunk Size", format_size(cfg.chunk_size))
    console.print(table)


@config.command(name="set")
@click.option("-u", "--username", help="Default SourceForge username.")
@click.option("-p", "--project", help="Default SourceForge project.")
@click.option("-k", "--key", help="Default SSH key path.")
@click.option("-m", "--mirror", help="Default download mirror.")
@click.option("-c", "--concurrency", type=int, help="Default download concurrency.")
@click.option("--pick-mirror", is_flag=True, help="Interactively select default mirror.")
def config_set(
    username: str | None,
    project: str | None,
    key: str | None,
    mirror: str | None,
    concurrency: int | None,
    pick_mirror: bool,
) -> None:
    """Update and persist default settings to config.toml."""
    cfg = Config.load()
    if username is not None:
        cfg.username = username
    if project is not None:
        cfg.project = project
    if key is not None:
        cfg.key_path = key
    if concurrency is not None:
        cfg.concurrency = concurrency
    if pick_mirror:
        cfg.default_mirror = prompt_mirror(console)
    elif mirror is not None:
        cfg.default_mirror = mirror

    cfg.save()
    console.print("[bold green]✓ Configuration saved.[/bold green]")
