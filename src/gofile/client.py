from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from gofile.api import (
    GoFileItem,
    create_guest_account,
    get_content,
    get_content_id,
    parse_content_items,
)
from gofile.config import Config
from gofile.downloader import download_file_async, prompt_select_file
from gofile.uploader import UploadResult, upload_file


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


class GoFileClient:
    """Unified client for GoFile upload, parallel chunked download, and browsing."""

    def __init__(
        self,
        token: str | None = None,
        concurrency: int | None = None,
        chunk_size: int | None = None,
        console: Console | None = None,
    ) -> None:
        cfg = Config.load()
        self.token = token or cfg.token
        self.concurrency = concurrency if concurrency is not None else cfg.concurrency
        self.chunk_size = chunk_size if chunk_size is not None else cfg.chunk_size
        self.console = console or Console()

    def ensure_token(self) -> str:
        """Ensure a valid account token is available, creating and saving a guest token if needed."""
        if self.token:
            return self.token

        cfg = Config.load()
        if cfg.token:
            self.token = cfg.token
            return self.token

        self.console.print(
            "[dim]No GoFile token found; creating anonymous guest account...[/dim]"
        )
        try:
            account = create_guest_account()
            self.token = account["token"]
            cfg.token = self.token
            cfg.account_id = account.get("account_id")
            cfg.root_folder = account.get("root_folder")
            cfg.save()
            return self.token
        except Exception as e:
            raise RuntimeError(
                f"Failed to auto-create GoFile guest account ({e}). "
                "Set your GoFile token via 'gf config set -t <token>' or env var GOFILE_TOKEN."
            ) from e

    # --- Download ---

    async def download_async(
        self,
        target: str,
        output_path: str | Path | None = None,
        password: str | None = None,
        concurrency: int | None = None,
        verify_checksum: bool = True,
        interactive: bool = True,
        download_all: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Path] | Path:
        token = self.ensure_token()
        content_id = get_content_id(target)

        content_data = get_content(
            content_id=content_id, token=token, password=password
        )
        items = parse_content_items(content_data)

        if not items:
            raise ValueError(f"No downloadable files found for '{target}'")

        # Single file
        if len(items) == 1 and not items[0].is_dir and items[0].link:
            item = items[0]
            return await download_file_async(
                url=item.link,
                token=token,
                filename=item.name,
                output_path=output_path,
                total_bytes=item.size,
                expected_md5=item.md5,
                concurrency=concurrency or self.concurrency,
                chunk_size=self.chunk_size,
                verify_checksum=verify_checksum,
                console=self.console,
                progress_callback=progress_callback,
            )

        # Folder with multiple items
        if download_all:
            results: list[Path] = []
            base_dir = (
                Path(output_path)
                if output_path
                else Path(content_data.get("name", content_id))
            )
            base_dir.mkdir(parents=True, exist_ok=True)
            for it in items:
                if not it.is_dir and it.link:
                    p = await download_file_async(
                        url=it.link,
                        token=token,
                        filename=it.name,
                        output_path=base_dir / it.name,
                        total_bytes=it.size,
                        expected_md5=it.md5,
                        concurrency=concurrency or self.concurrency,
                        chunk_size=self.chunk_size,
                        verify_checksum=verify_checksum,
                        console=self.console,
                        progress_callback=progress_callback,
                    )
                    results.append(p)
            return results

        # Interactive single file choice
        chosen = items[0]
        if interactive and sys.stdin.isatty():
            chosen = prompt_select_file(items, console=self.console)
        elif [it for it in items if not it.is_dir]:
            chosen = next(it for it in items if not it.is_dir)

        if not chosen.link:
            raise ValueError(
                f"Selected item '{chosen.name}' does not have a direct download link."
            )

        return await download_file_async(
            url=chosen.link,
            token=token,
            filename=chosen.name,
            output_path=output_path,
            total_bytes=chosen.size,
            expected_md5=chosen.md5,
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
        password: str | None = None,
        concurrency: int | None = None,
        verify_checksum: bool = True,
        interactive: bool = True,
        download_all: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Path] | Path:
        return _run_sync(
            self.download_async(
                target=target,
                output_path=output_path,
                password=password,
                concurrency=concurrency,
                verify_checksum=verify_checksum,
                interactive=interactive,
                download_all=download_all,
                progress_callback=progress_callback,
            )
        )

    # --- Upload ---

    async def upload_async(
        self,
        file_path: str | Path,
        folder_id: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadResult:
        token = self.token or Config.load().token
        res = await asyncio.to_thread(
            upload_file,
            file_path=file_path,
            token=token,
            folder_id=folder_id,
            console=self.console,
            progress_callback=progress_callback,
        )
        if res.guest_token:
            self.token = res.guest_token
            cfg = Config.load()
            if not cfg.token:
                cfg.token = res.guest_token
                cfg.save()
        return res

    def upload(
        self,
        file_path: str | Path,
        folder_id: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadResult:
        token = self.token or Config.load().token
        res = upload_file(
            file_path=file_path,
            token=token,
            folder_id=folder_id,
            console=self.console,
            progress_callback=progress_callback,
        )
        if res.guest_token:
            self.token = res.guest_token
            cfg = Config.load()
            if not cfg.token:
                cfg.token = res.guest_token
                cfg.save()
        return res

    # --- List ---

    def list(
        self,
        target: str,
        password: str | None = None,
    ) -> list[GoFileItem]:
        token = self.ensure_token()
        content_id = get_content_id(target)
        data = get_content(content_id=content_id, token=token, password=password)
        return parse_content_items(data)
