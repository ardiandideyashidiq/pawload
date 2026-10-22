from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path

from curl_cffi import requests
from rich.console import Console

from sourceforge.config import Config
from sourceforge.downloader import download_file_async
from sourceforge.mirrors import CLI_USER_AGENT
from sourceforge.sftp import (
    RemoteItem,
    delete_remote_file_sftp,
    list_files_sftp,
    open_sftp,
    rename_remote_file_sftp,
    upload_file_sftp,
)


def list_files_rss(project: str, remote_dir: str = "") -> list[RemoteItem]:
    """List project files unauthenticated via public SourceForge RSS feed."""
    clean_sub = remote_dir.strip().strip("/")
    rss_url = f"https://sourceforge.net/projects/{project}/rss?path=/{clean_sub}"
    resp = requests.get(rss_url, headers={"User-Agent": CLI_USER_AGENT}, timeout=15)
    if resp.status_code != 200:
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return []

    namespaces = {
        "media": "http://video.search.yahoo.com/mrss/",
        "files": "https://sourceforge.net/api/files.rdf#",
    }

    items: list[RemoteItem] = []
    for item in root.findall(".//item"):
        title_elem = item.find("title")
        if title_elem is None or not title_elem.text:
            continue
        raw_title = title_elem.text.strip()
        filename = raw_title.split("/")[-1]

        # Extract size
        size = 0
        media_content = item.find(".//media:content", namespaces)
        if media_content is not None:
            size_attr = media_content.get("filesize")
            if size_attr and size_attr.isdigit():
                size = int(size_attr)

        # Extract MD5
        md5 = None
        hash_elem = item.find(".//media:hash", namespaces)
        if hash_elem is not None and hash_elem.text:
            md5 = hash_elem.text.strip().lower()

        # Extract pubDate
        mtime = None
        pub_date = item.find("pubDate")
        if pub_date is not None and pub_date.text:
            try:
                mtime = parsedate_to_datetime(pub_date.text.strip()).astimezone(UTC)
            except Exception:
                pass

        items.append(
            RemoteItem(
                name=filename,
                path=raw_title,
                is_dir=False,
                size=size,
                modified_time=mtime,
                md5=md5,
            )
        )

    return sorted(items, key=lambda x: x.name.lower())


def _run_sync(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class SourceForgeClient:
    """Unified client for SourceForge download, upload, and FRS management."""

    def __init__(
        self,
        project: str | None = None,
        username: str | None = None,
        key_path: str | None = None,
        password: str | None = None,
        default_mirror: str | None = None,
        concurrency: int | None = None,
        chunk_size: int | None = None,
        console: Console | None = None,
    ) -> None:
        cfg = Config.load()
        self.project = project or cfg.project
        self.username = username or cfg.username
        self.key_path = key_path or cfg.key_path
        self.password = password or cfg.password
        self.default_mirror = default_mirror or cfg.default_mirror
        self.concurrency = concurrency if concurrency is not None else cfg.concurrency
        self.chunk_size = chunk_size if chunk_size is not None else cfg.chunk_size
        self.console = console or Console()

    def _require_project(self) -> str:
        if not self.project:
            raise ValueError("SourceForge project name is required. Set via parameter, SF_PROJECT env, or config.")
        return self.project

    def _require_username(self) -> str:
        if not self.username:
            raise ValueError("SourceForge username is required for upload/SFTP operations. Set via SF_USERNAME env or config.")
        return self.username

    # --- Download ---

    async def download_async(
        self,
        remote_path: str,
        output_path: str | Path | None = None,
        mirror: str | None = None,
        concurrency: int | None = None,
        verify_checksum: bool = True,
        interactive_prompt: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        project = self._require_project()
        return await download_file_async(
            project=project,
            remote_path=remote_path,
            output_path=output_path,
            mirror=mirror or self.default_mirror,
            concurrency=concurrency or self.concurrency,
            chunk_size=self.chunk_size,
            verify_checksum=verify_checksum,
            interactive_prompt=interactive_prompt,
            console=self.console,
            progress_callback=progress_callback,
        )

    def download(
        self,
        remote_path: str,
        output_path: str | Path | None = None,
        mirror: str | None = None,
        concurrency: int | None = None,
        verify_checksum: bool = True,
        interactive_prompt: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        return _run_sync(
            self.download_async(
                remote_path=remote_path,
                output_path=output_path,
                mirror=mirror,
                concurrency=concurrency,
                verify_checksum=verify_checksum,
                interactive_prompt=interactive_prompt,
                progress_callback=progress_callback,
            )
        )

    # --- Upload ---

    async def upload_async(
        self,
        local_path: str | Path,
        remote_dir: str = "",
        force: bool = False,
        interactive: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        project = self._require_project()
        username = self._require_username()
        async with open_sftp(username=username, key_path=self.key_path, password=self.password) as sftp:
            return await upload_file_sftp(
                sftp=sftp,
                local_path=local_path,
                project=project,
                remote_dir=remote_dir,
                force=force,
                interactive=interactive,
                console=self.console,
                progress_callback=progress_callback,
            )

    def upload(
        self,
        local_path: str | Path,
        remote_dir: str = "",
        force: bool = False,
        interactive: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        return _run_sync(
            self.upload_async(
                local_path=local_path,
                remote_dir=remote_dir,
                force=force,
                interactive=interactive,
                progress_callback=progress_callback,
            )
        )

    # --- List ---

    async def list_async(
        self,
        remote_dir: str = "",
        use_sftp: bool | None = None,
    ) -> list[RemoteItem]:
        project = self._require_project()
        # Prefer SFTP if credentials available and use_sftp is not explicitly False
        should_sftp = use_sftp if use_sftp is not None else (self.username is not None and (self.key_path is not None or self.password is not None))
        if should_sftp and self.username:
            try:
                async with open_sftp(username=self.username, key_path=self.key_path, password=self.password) as sftp:
                    return await list_files_sftp(sftp=sftp, project=project, remote_dir=remote_dir)
            except Exception as e:
                self.console.print(f"[yellow]SFTP list failed ({e}); falling back to public RSS feed.[/yellow]")

        return list_files_rss(project=project, remote_dir=remote_dir)

    def list(
        self,
        remote_dir: str = "",
        use_sftp: bool | None = None,
    ) -> list[RemoteItem]:
        return _run_sync(self.list_async(remote_dir=remote_dir, use_sftp=use_sftp))

    # --- Delete ---

    async def delete_async(self, remote_path: str) -> None:
        project = self._require_project()
        username = self._require_username()
        async with open_sftp(username=username, key_path=self.key_path, password=self.password) as sftp:
            await delete_remote_file_sftp(sftp=sftp, project=project, remote_path=remote_path)
            self.console.print(f"[bold green]✓ Deleted remote path:[/bold green] {remote_path}")

    def delete(self, remote_path: str) -> None:
        return _run_sync(self.delete_async(remote_path=remote_path))

    # --- Rename ---

    async def rename_async(self, old_remote_path: str, new_remote_path: str) -> None:
        project = self._require_project()
        username = self._require_username()
        async with open_sftp(username=username, key_path=self.key_path, password=self.password) as sftp:
            await rename_remote_file_sftp(
                sftp=sftp,
                project=project,
                old_remote_path=old_remote_path,
                new_remote_path=new_remote_path,
            )
            self.console.print(f"[bold green]✓ Renamed:[/bold green] {old_remote_path} -> {new_remote_path}")

    def rename(self, old_remote_path: str, new_remote_path: str) -> None:
        return _run_sync(self.rename_async(old_remote_path=old_remote_path, new_remote_path=new_remote_path))
