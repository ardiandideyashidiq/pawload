from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import asyncssh
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm

SF_FRS_HOST = "frs.sourceforge.net"
SF_FRS_PORT = 22
SF_FRS_ROOT = "/home/frs/project"


@dataclass
class RemoteItem:
    name: str
    path: str
    is_dir: bool
    size: int
    modified_time: datetime | None = None
    md5: str | None = None


@asynccontextmanager
async def open_sftp(
    username: str,
    key_path: str | None = None,
    password: str | None = None,
    host: str = SF_FRS_HOST,
    port: int = SF_FRS_PORT,
) -> AsyncIterator[asyncssh.sftp.SFTPClient]:
    """Connect to SourceForge FRS and open an SFTP client session."""
    client_keys = [key_path] if key_path else None
    conn_kwargs: dict = {
        "host": host,
        "port": port,
        "username": username,
        "known_hosts": None,  # SourceForge FRS host keys vary across pool
    }
    if client_keys:
        conn_kwargs["client_keys"] = client_keys
    if password:
        conn_kwargs["password"] = password

    async with asyncssh.connect(**conn_kwargs) as conn, conn.start_sftp_client() as sftp:
        yield sftp


def get_remote_project_dir(project: str, subpath: str = "") -> str:
    clean_sub = subpath.strip().strip("/")
    if clean_sub:
        return f"{SF_FRS_ROOT}/{project}/{clean_sub}"
    return f"{SF_FRS_ROOT}/{project}"


async def upload_file_sftp(
    sftp: asyncssh.sftp.SFTPClient,
    local_path: str | Path,
    project: str,
    remote_dir: str = "",
    force: bool = False,
    interactive: bool = True,
    console: Console | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> str:
    con = console or Console()
    local_file = Path(local_path)
    if not local_file.is_file():
        raise FileNotFoundError(f"Local file does not exist: {local_file}")

    target_dir = get_remote_project_dir(project, remote_dir)
    target_file = f"{target_dir}/{local_file.name}"

    # Auto-create remote directories recursively (mkdir -p)
    if not await sftp.exists(target_dir):
        con.print(f"[dim]Creating remote directory: {target_dir}[/dim]")
        await sftp.makedirs(target_dir, exist_ok=True)

    # Collision check
    if await sftp.exists(target_file) and not force:
        if interactive and sys.stdin.isatty():
            overwrite = Confirm.ask(
                f"[yellow]Remote file '{target_file}' already exists. Overwrite?[/yellow]",
                default=False,
            )
            if not overwrite:
                con.print("[yellow]Upload cancelled by user.[/yellow]")
                return target_file
        else:
            raise FileExistsError(
                f"Remote file '{target_file}' already exists. Use --force to overwrite."
            )

    file_size = local_file.stat().st_size

    with Progress(
        TextColumn("[bold green]Uploading", justify="right"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=con,
    ) as progress:
        task = progress.add_task("upload", total=file_size)

        def sftp_progress_handler(src: bytes, dst: bytes, copied: int, total: int) -> None:
            progress.update(task, completed=copied, total=total)
            if progress_callback:
                progress_callback(copied, total)

        await sftp.put(
            str(local_file),
            target_file,
            progress_handler=sftp_progress_handler,
        )

    con.print(f"[bold green]✓ Successfully uploaded:[/bold green] {local_file.name} -> {target_file}")
    return target_file


async def list_files_sftp(
    sftp: asyncssh.sftp.SFTPClient,
    project: str,
    remote_dir: str = "",
) -> list[RemoteItem]:
    target_dir = get_remote_project_dir(project, remote_dir)
    if not await sftp.exists(target_dir):
        return []

    items: list[RemoteItem] = []
    file_attrs = await sftp.readdir(target_dir)
    for attr in file_attrs:
        name = attr.filename
        if name in (".", ".."):
            continue
        is_dir = (attr.attrs.permissions & 0o170000) == 0o040000 if attr.attrs.permissions else False
        mtime = datetime.fromtimestamp(attr.attrs.mtime, tz=UTC) if attr.attrs.mtime else None
        items.append(
            RemoteItem(
                name=name,
                path=f"{target_dir}/{name}",
                is_dir=is_dir,
                size=attr.attrs.size or 0,
                modified_time=mtime,
            )
        )
    return sorted(items, key=lambda x: (not x.is_dir, x.name.lower()))


async def delete_remote_file_sftp(
    sftp: asyncssh.sftp.SFTPClient,
    project: str,
    remote_path: str,
) -> None:
    target_path = get_remote_project_dir(project, remote_path)
    if not await sftp.exists(target_path):
        raise FileNotFoundError(f"Remote path not found: {target_path}")

    stat = await sftp.stat(target_path)
    is_dir = (stat.permissions & 0o170000) == 0o040000 if stat.permissions else False
    if is_dir:
        await sftp.rmdir(target_path)
    else:
        await sftp.remove(target_path)


async def rename_remote_file_sftp(
    sftp: asyncssh.sftp.SFTPClient,
    project: str,
    old_remote_path: str,
    new_remote_path: str,
) -> None:
    old_target = get_remote_project_dir(project, old_remote_path)
    new_target = get_remote_project_dir(project, new_remote_path)
    if not await sftp.exists(old_target):
        raise FileNotFoundError(f"Source remote path not found: {old_target}")

    await sftp.rename(old_target, new_target)
