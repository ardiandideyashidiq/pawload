from __future__ import annotations

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

import sourceforge.config as sf_cfg
from sourceforge.client import SourceForgeClient
from sourceforge.config import Config, format_size, setup_logging
from sourceforge.mirrors import prompt_mirror
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
    """SourceForge CLI: Upload, download, and manage FRS releases."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.argument("target")
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-o", "--output", help="Destination file or directory path.")
@click.option(
    "-m",
    "--mirror",
    help="Mirror ID (e.g., cfhcable, delska, twds, master, autoselect).",
)
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
    help="Verify MD5 checksum against SourceForge metadata.",
)
@click.option(
    "--prompt/--no-prompt",
    default=True,
    help="Interactively prompt for mirror region if not set.",
)
@click.option(
    "--latest",
    is_flag=True,
    help="Download latest release automatically without listing or prompting.",
)
@click.option(
    "-n",
    "--notify",
    is_flag=True,
    help="Stream progress and send completion alert to Telegram.",
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
    project: str | None,
    output: str | None,
    mirror: str | None,
    concurrency: int | None,
    verify: bool,
    prompt: bool,
    latest: bool,
    notify: bool,
    verbose: int,
) -> None:
    """Download a file or project release with parallel chunks, resume support, and checksum verification."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    reporter = (
        create_reporter(title=f"SourceForge: {target}", target_name="SourceForge")
        if notify
        else None
    )
    cb = (lambda delta, tot: reporter.advance(delta, tot)) if reporter else None
    try:
        client = SourceForgeClient(project=project, console=console)
        dest = client.download(
            target=target,
            output_path=output,
            mirror=mirror,
            concurrency=concurrency,
            verify_checksum=verify,
            interactive_prompt=prompt,
            latest=latest,
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


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-d", "--remote-dir", default="", help="Remote subfolder within project.")
@click.option("-u", "--username", help="SourceForge username.")
@click.option("-k", "--key", help="Path to SSH private key.")
@click.option(
    "-f", "--force", is_flag=True, help="Overwrite remote file if it already exists."
)
@click.option(
    "-n",
    "--notify",
    is_flag=True,
    help="Stream progress and send completion alert to Telegram.",
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
    project: str | None,
    remote_dir: str,
    username: str | None,
    key: str | None,
    force: bool,
    notify: bool,
    verbose: int,
) -> None:
    """Upload a file via SFTP with automatic directory creation and resume support."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    reporter = (
        create_reporter(title=f"SourceForge: {file.name}", target_name="SourceForge")
        if notify
        else None
    )
    cb = (lambda copied, tot: reporter.update(copied, tot)) if reporter else None
    try:
        client = SourceForgeClient(
            project=project, username=username, key_path=key, console=console
        )
        remote_target = client.upload(
            local_path=file,
            remote_dir=remote_dir,
            force=force,
            interactive=True,
            progress_callback=cb,
        )
        if reporter:
            reporter.finish(success_url=str(remote_target))
        console.print(f"[bold green]✓ Upload complete:[/bold green] {remote_target}")
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


@cli.command(name="list")
@click.argument("remote_dir", default="", required=False)
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-u", "--username", help="SourceForge username (uses SFTP if provided).")
@click.option(
    "--rss", is_flag=True, help="Force unauthenticated public RSS feed listing."
)
@click.option("--sftp", is_flag=True, help="Force SFTP real-time filesystem listing.")
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
    remote_dir: str,
    project: str | None,
    username: str | None,
    rss: bool,
    sftp: bool,
    verbose: int,
) -> None:
    """List remote files and folders in project."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        if remote_dir.startswith(("http://", "https://")):
            from sourceforge.mirrors import parse_target

            info = parse_target(remote_dir, project=project)
            project = info.project
            remote_dir = info.remote_path if "/" in info.remote_path else ""

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
            mtime_str = (
                item.modified_time.strftime("%Y-%m-%d %H:%M:%S")
                if item.modified_time
                else "-"
            )
            md5_str = item.md5 or "-"
            table.add_row(item_type, item.name, size_str, mtime_str, md5_str)

        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]List Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("remote_path")
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-u", "--username", help="SourceForge username.")
@click.option("-k", "--key", help="Path to SSH private key.")
@click.option("-f", "--force", is_flag=True, help="Confirm deletion without prompting.")
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def delete(
    ctx: click.Context,
    remote_path: str,
    project: str | None,
    username: str | None,
    key: str | None,
    force: bool,
    verbose: int,
) -> None:
    """Delete a remote file or folder via SFTP."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    if not force:
        from rich.prompt import Confirm

        if not Confirm.ask(
            f"[yellow]Are you sure you want to delete remote path '{remote_path}'?[/yellow]"
        ):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        client = SourceForgeClient(
            project=project, username=username, key_path=key, console=console
        )
        client.delete(remote_path=remote_path)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Delete Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("old_path")
@click.argument("new_path")
@click.option("-p", "--project", help="SourceForge project name.")
@click.option("-u", "--username", help="SourceForge username.")
@click.option("-k", "--key", help="Path to SSH private key.")
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging (-v for INFO, -vv for DEBUG).",
)
@click.pass_context
def rename(
    ctx: click.Context,
    old_path: str,
    new_path: str,
    project: str | None,
    username: str | None,
    key: str | None,
    verbose: int,
) -> None:
    """Rename or move a remote file or folder via SFTP."""
    lvl = max(ctx.obj.get("verbose", 0) if ctx.obj else 0, verbose)
    setup_logging(lvl)
    try:
        client = SourceForgeClient(
            project=project, username=username, key_path=key, console=console
        )
        client.rename(old_remote_path=old_path, new_remote_path=new_path)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Rename Error:[/bold red] {e}")
        sys.exit(1)


@cli.group()
def config() -> None:
    """Manage local SourceForge CLI configuration profile."""


@config.command(name="show")
@click.option(
    "--all",
    "-a",
    "show_all",
    is_flag=True,
    help="Display all configured services in unified config.",
)
def config_show(show_all: bool) -> None:
    """Show current configuration settings."""
    console.print(f"[dim]Config file: {sf_cfg.CONFIG_FILE}[/dim]")
    if show_all:
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
        return

    cfg = Config.load()
    table = Table(title="SourceForge Configuration")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Username", cfg.username or "[dim](not set)[/dim]")
    table.add_row("Project", cfg.project or "[dim](not set)[/dim]")
    table.add_row("SSH Key", cfg.key_path or "[dim](not set)[/dim]")
    table.add_row("Default Mirror", cfg.default_mirror or "[dim](not set)[/dim]")
    table.add_row("Concurrency", str(cfg.concurrency))
    table.add_row("Chunk Size", format_size(cfg.chunk_size))
    console.print(table)


@config.command(name="path")
def config_path() -> None:
    """Print active configuration file path."""
    console.print(str(sf_cfg.CONFIG_FILE))


@config.command(name="set")
@click.option("-u", "--username", help="Default SourceForge username.")
@click.option("-p", "--project", help="Default SourceForge project.")
@click.option("-k", "--key", help="Default SSH key path.")
@click.option("-m", "--mirror", help="Default download mirror.")
@click.option("-c", "--concurrency", type=int, help="Default download concurrency.")
@click.option(
    "--pick-mirror", is_flag=True, help="Interactively select default mirror."
)
def config_set(
    username: str | None,
    project: str | None,
    key: str | None,
    mirror: str | None,
    concurrency: int | None,
    pick_mirror: bool,
) -> None:
    try:
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
            cfg.default_mirror = prompt_mirror(
                project=cfg.project or project, console=console
            )
        elif mirror is not None:
            cfg.default_mirror = mirror

        cfg.save()
        console.print("[bold green]✓ Configuration saved.[/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)


@cli.command("web")
@click.option(
    "--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)."
)
@click.option("--port", type=int, default=8765, help="Port to bind (default: 8765).")
@click.option(
    "--open-browser/--no-browser",
    default=True,
    help="Automatically open web browser.",
)
def web_cmd(host: str, port: int, open_browser: bool) -> None:
    """Launch MultiCloud Web Transfer Dashboard (Flask + Tailwind CSS)."""
    from web.app import run_server

    run_server(host=host, port=port, open_browser=open_browser)


@cli.command("serve")
@click.option(
    "--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)."
)
@click.option("--port", type=int, default=8765, help="Port to bind (default: 8765).")
@click.option(
    "--open-browser/--no-browser",
    default=True,
    help="Automatically open web browser.",
)
def serve_cmd(host: str, port: int, open_browser: bool) -> None:
    """Launch MultiCloud Web Transfer Dashboard (Flask + Tailwind CSS)."""
    from web.app import run_server

    run_server(host=host, port=port, open_browser=open_browser)


@cli.command("gui")
@click.option(
    "--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)."
)
@click.option("--port", type=int, default=8765, help="Port to bind (default: 8765).")
@click.option(
    "--open-browser/--no-browser",
    default=True,
    help="Automatically open web browser.",
)
def gui_cmd(host: str, port: int, open_browser: bool) -> None:
    """Launch MultiCloud Web Transfer Dashboard (alias for sf web)."""
    from web.app import run_server

    run_server(host=host, port=port, open_browser=open_browser)
