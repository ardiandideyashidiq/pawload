from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

from gdrive.api import (
    GDriveItem,
    extract_gdrive_id,
    inspect_target,
    inspect_target_async,
    list_folder,
    load_cookies,
    resolve_direct_download,
)
from gdrive.config import Config
from gdrive.downloader import download_file_async


def _run_sync(coro: Any) -> Any:
    """Run an async coroutine synchronously, avoiding event loop collisions."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class GDriveClient:
    """Unified client for Google Drive target inspection, URL resolution, and downloading."""

    def __init__(
        self,
        cookie_file: str | Path | None = None,
        cookies: dict[str, str] | str | Path | None = None,
        concurrency: int | None = None,
        console: Console | None = None,
    ) -> None:
        cfg = Config.load()
        cookie_src = cookies if cookies is not None else cookie_file
        self.cookie_file = str(cookie_src) if cookie_src and not isinstance(cookie_src, dict) else cfg.cookie_file
        self.cookies = load_cookies(cookie_src) if cookie_src is not None else load_cookies(self.cookie_file)
        self.concurrency = concurrency or cfg.concurrency or 4
        self.console = console or Console()

    def info(self, target: str) -> GDriveItem:
        """Inspect target URL or ID to get metadata (filename, size, folder status, children)."""
        return inspect_target(target, cookies=self.cookies)

    async def info_async(self, target: str) -> GDriveItem:
        """Inspect target URL or ID asynchronously."""
        return await inspect_target_async(target, cookies=self.cookies)

    def list(self, folder_id: str) -> list[GDriveItem]:
        """List files in a Google Drive folder."""
        return list_folder(folder_id, cookies=self.cookies)

    async def get_direct_url_async(self, target: str) -> tuple[str, str, int]:
        """Resolve direct download URL, filename, and file size."""
        clean_id = extract_gdrive_id(target)
        info = await self.info_async(target)
        if info.is_folder:
            if not info.children:
                raise RuntimeError(f"Google Drive folder '{info.name}' ({info.id}) has no files.")
            clean_id = info.children[0].id
        return await resolve_direct_download(clean_id, cookies=self.cookies)

    def get_direct_url(self, target: str) -> tuple[str, str, int]:
        """Resolve direct download URL synchronously."""
        return _run_sync(self.get_direct_url_async(target))

    async def download_async(
        self,
        target: str,
        output_path: str | Path | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Download file asynchronously with chunk workers and resume support."""
        workers = concurrency or self.concurrency
        return await download_file_async(
            target=target,
            output_path=output_path,
            cookies=self.cookies,
            concurrency=workers,
            console=self.console,
            progress_callback=progress_callback,
        )

    def download(
        self,
        target: str,
        output_path: str | Path | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Download file synchronously."""
        return _run_sync(
            self.download_async(
                target=target,
                output_path=output_path,
                concurrency=concurrency,
                progress_callback=progress_callback,
            )
        )
