from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from vikingfile.api import (
    VikingItem,
    check_file,
    delete_file,
    extract_file_hash,
    list_files,
    rename_file,
)
from vikingfile.config import Config
from vikingfile.downloader import download_file_async
from vikingfile.uploader import UploadResult, upload_file


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


class VikingFileClient:
    """Unified client for VikingFile upload, download, and management."""

    def __init__(
        self,
        user: str | None = None,
        concurrency: int | None = None,
        chunk_size: int | None = None,
        console: Console | None = None,
    ) -> None:
        cfg = Config.load()
        self.user = user if user is not None else cfg.user
        self.concurrency = concurrency if concurrency is not None else cfg.concurrency
        self.chunk_size = chunk_size if chunk_size is not None else cfg.chunk_size
        self.console = console or Console()

    # --- Upload ---

    async def upload_async(
        self,
        file_path: str | Path,
        remote_path: str = "",
    ) -> UploadResult:
        return await asyncio.to_thread(
            upload_file,
            file_path=file_path,
            user=self.user,
            remote_path=remote_path,
            console=self.console,
        )

    def upload(
        self,
        file_path: str | Path,
        remote_path: str = "",
    ) -> UploadResult:
        return upload_file(
            file_path=file_path,
            user=self.user,
            remote_path=remote_path,
            console=self.console,
        )

    # --- Check / Info ---

    def check(self, target: str) -> VikingItem | None:
        return check_file(target)

    # --- List ---

    def list(
        self,
        page: int = 1,
        remote_path: str = "",
    ) -> list[VikingItem]:
        return list_files(user=self.user, page=page, remote_path=remote_path)

    # --- Delete ---

    def delete(self, target: str) -> bool:
        if not self.user:
            raise ValueError("User hash is required to delete files. Set via VIKINGFILE_USER or config.")
        return delete_file(file_hash=target, user=self.user)

    # --- Rename ---

    def rename(self, target: str, new_filename: str) -> bool:
        if not self.user:
            raise ValueError("User hash is required to rename files. Set via VIKINGFILE_USER or config.")
        return rename_file(file_hash=target, user=self.user, new_filename=new_filename)

    # --- Download ---

    async def download_async(
        self,
        target: str,
        output_path: str | Path | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        clean = target.strip()
        # Direct download URL
        if clean.startswith(("http://", "https://")) and "/f/" not in clean:
            filename = clean.split("?")[0].rstrip("/").split("/")[-1] or "downloaded_file"
            return await download_file_async(
                url=clean,
                filename=filename,
                output_path=output_path,
                concurrency=concurrency or self.concurrency,
                chunk_size=self.chunk_size,
                console=self.console,
                progress_callback=progress_callback,
            )

        # File share link or hash
        file_hash = extract_file_hash(clean)
        info = check_file(file_hash)
        if not info or not info.exist:
            raise FileNotFoundError(f"File '{file_hash}' does not exist on VikingFile.")

        filename = info.name
        # Note: Turnstile protected web downloads cannot be automated headlessly; direct downloads require direct server link
        raise NotImplementedError(
            f"VikingFile '{info.name}' ({info.size} bytes) is protected by Turnstile CAPTCHA on the web view. "
            "Pass the direct download link or use upload/check/list API."
        )

    def download(
        self,
        target: str,
        output_path: str | Path | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        return _run_sync(
            self.download_async(
                target=target,
                output_path=output_path,
                concurrency=concurrency,
                progress_callback=progress_callback,
            )
        )
