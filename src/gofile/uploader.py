from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests
from curl_cffi.curl import CurlMime
from loguru import logger
from rich.console import Console

from gofile.api import UPLOAD_URL


@dataclass
class UploadResult:
    download_page: str
    file_id: str
    filename: str
    parent_folder: str
    guest_token: str | None = None


def upload_file(
    file_path: str | Path,
    token: str | None = None,
    folder_id: str | None = None,
    console: Console | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> UploadResult:
    con = console or Console()
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Local file not found: {path}")

    total_size = path.stat().st_size
    logger.info("Starting GoFile upload: {} ({} bytes)", path.name, total_size)
    mp = CurlMime()
    if token:
        mp.addpart(name="token", data=token.encode())
    if folder_id:
        mp.addpart(name="folderId", data=folder_id.encode())
    mp.addpart(name="file", filename=path.name, local_path=str(path))

    with con.status(f"[cyan]Uploading {path.name} ({total_size} bytes)...[/cyan]"):
        try:
            resp = requests.post(
                UPLOAD_URL,
                multipart=mp,
                timeout=300,
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            con.print("\n[yellow]Upload cancelled by user.[/yellow]")
            raise KeyboardInterrupt
        finally:
            mp.close()

    if resp.status_code != 200:
        raise RuntimeError(f"GoFile upload failed: HTTP {resp.status_code}")

    res_data = resp.json()
    if res_data.get("status") != "ok":
        msg = res_data.get("status") or "upload error"
        raise RuntimeError(f"GoFile upload error: {msg}")

    d = res_data["data"]
    download_page = d.get("downloadPage") or f"https://gofile.io/d/{d.get('parentFolderCode', d.get('parentFolder', ''))}"
    guest_token = d.get("guestToken")
    logger.info("GoFile upload complete: {}", download_page)

    con.print(f"[bold green]✓ Upload complete:[/bold green] {download_page}")
    return UploadResult(
        download_page=download_page,
        file_id=d.get("fileId", d.get("id", "")),
        filename=d.get("fileName", d.get("name", path.name)),
        parent_folder=d.get("parentFolder", ""),
        guest_token=guest_token,
    )
