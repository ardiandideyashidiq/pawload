from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from pixeldrain.api import (
    PixelDrainItem,
    delete_file,
    extract_file_id,
    get_file_info,
    get_list,
)
from pixeldrain.config import Config
from pixeldrain.downloader import download_file_async
from pixeldrain.uploader import UploadResult, upload_file


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


class PixelDrainClient:
    """Unified client for Pixeldrain upload, download, and file management."""

    def __init__(
        self,
        api_key: str | None = None,
        concurrency: int | None = None,
        chunk_size: int | None = None,
        console: Console | None = None,
    ) -> None:
        cfg = Config.load()
        self.api_key = api_key if api_key is not None else cfg.api_key
        self.concurrency = concurrency if concurrency is not None else cfg.concurrency
        self.chunk_size = chunk_size if chunk_size is not None else cfg.chunk_size
        self.console = console or Console()

    # --- Info ---

    def info(self, target: str) -> PixelDrainItem | None:
        file_id = extract_file_id(target)
        return get_file_info(file_id, api_key=self.api_key)

    # --- List ---

    def list(self, list_id: str) -> list[PixelDrainItem]:
        clean_id = extract_file_id(list_id)
        return get_list(clean_id, api_key=self.api_key)

    # --- Upload ---

    async def upload_async(self, file_path: str | Path) -> UploadResult:
        return await asyncio.to_thread(
            upload_file,
            file_path=file_path,
            api_key=self.api_key,
            console=self.console,
        )

    def upload(self, file_path: str | Path) -> UploadResult:
        return upload_file(
            file_path=file_path,
            api_key=self.api_key,
            console=self.console,
        )

    # --- Delete ---

    def delete(self, target: str) -> bool:
        if not self.api_key:
            raise ValueError("API key is required to delete Pixeldrain files. Set via PIXELDRAIN_API_KEY or config.")
        file_id = extract_file_id(target)
        return delete_file(file_id, api_key=self.api_key)

    # --- Download ---

    async def download_async(
        self,
        target: str,
        output_path: str | Path | None = None,
        concurrency: int | None = None,
        verify_checksum: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        file_id = extract_file_id(target)
        info = get_file_info(file_id, api_key=self.api_key)

        filename = info.name if info else f"{file_id}.bin"
        total_size = info.size if info else 0
        expected_sha256 = info.sha256_hash if info else None

        if info and not info.can_download:
            raise PermissionError(f"Pixeldrain file '{file_id}' is restricted or cannot be downloaded.")

        return await download_file_async(
            file_id=file_id,
            filename=filename,
            output_path=output_path,
            total_bytes=total_size,
            expected_sha256=expected_sha256,
            api_key=self.api_key,
            concurrency=concurrency or self.concurrency,
            chunk_size=self.chunk_size,
            verify_checksum=verify_checksum,
            console=self.console,
            progress_callback=progress_callback,
        )

    def download(
        self,
        target: str,
        output_path: str | Path | None = None,
        concurrency: int | None = None,
        verify_checksum: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        return _run_sync(
            self.download_async(
                target=target,
                output_path=output_path,
                concurrency=concurrency,
                verify_checksum=verify_checksum,
                progress_callback=progress_callback,
            )
        )
