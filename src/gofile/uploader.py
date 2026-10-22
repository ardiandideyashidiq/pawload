from __future__ import annotations

import asyncio
import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from gofile.api import UPLOAD_URL, USER_AGENT


@dataclass
class UploadResult:
    download_page: str
    file_id: str
    filename: str
    parent_folder: str
    guest_token: str | None = None


class ProgressFileReader(io.BufferedReader):
    """File reader wrapper that reports read progress for uploads."""

    def __init__(
        self,
        filepath: Path,
        progress_cb: Callable[[int, int], None],
    ) -> None:
        raw = io.FileIO(str(filepath), "rb")
        super().__init__(raw)
        self.total_size = filepath.stat().st_size
        self.bytes_read = 0
        self.progress_cb = progress_cb

    def read(self, size: int = -1) -> bytes:
        chunk = super().read(size)
        if chunk:
            self.bytes_read += len(chunk)
            self.progress_cb(self.bytes_read, self.total_size)
        return chunk


def upload_file(
    file_path: str | Path,
    token: str,
    folder_id: str | None = None,
    console: Console | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> UploadResult:
    con = console or Console()
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Local file not found: {path}")

    total_size = path.stat().st_size
    data_payload: dict[str, str] = {"token": token}
    if folder_id:
        data_payload["folderId"] = folder_id

    with Progress(
        TextColumn("[bold green]Uploading", justify="right"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=con,
    ) as progress:
        task = progress.add_task("upload", total=total_size)

        def cb(copied: int, total: int) -> None:
            progress.update(task, completed=copied, total=total)
            if progress_callback:
                progress_callback(copied, total)

        reader = ProgressFileReader(path, cb)
        try:
            resp = requests.post(
                UPLOAD_URL,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                data=data_payload,
                files={"file": (path.name, reader)},
                timeout=300,
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            con.print("\n[yellow]Upload cancelled by user.[/yellow]")
            raise KeyboardInterrupt
        finally:
            reader.close()

    if resp.status_code != 200:
        raise RuntimeError(f"GoFile upload failed: HTTP {resp.status_code}")

    res_data = resp.json()
    if res_data.get("status") != "ok":
        msg = res_data.get("status") or "upload error"
        raise RuntimeError(f"GoFile upload error: {msg}")

    d = res_data["data"]
    download_page = d.get("downloadPage") or f"https://gofile.io/d/{d.get('parentFolder', '')}"

    con.print(f"[bold green]✓ Upload complete:[/bold green] {download_page}")
    return UploadResult(
        download_page=download_page,
        file_id=d.get("fileId", ""),
        filename=d.get("fileName", path.name),
        parent_folder=d.get("parentFolder", ""),
    )
