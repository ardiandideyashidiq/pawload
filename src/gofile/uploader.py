from __future__ import annotations

import asyncio
import io
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from curl_cffi.curl import Curl, CurlInfo, CurlOpt
from loguru import logger
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

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
    boundary = f"----PawloadBoundary{uuid.uuid4().hex}"

    parts_bytes = bytearray()
    if token:
        parts_bytes.extend(
            f'--{boundary}\r\nContent-Disposition: form-data; name="token"\r\n\r\n{token}\r\n'.encode(
                "utf-8"
            )
        )
    if folder_id:
        parts_bytes.extend(
            f'--{boundary}\r\nContent-Disposition: form-data; name="folderId"\r\n\r\n{folder_id}\r\n'.encode(
                "utf-8"
            )
        )

    file_header = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    parts_bytes.extend(file_header)
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")

    content_length = len(parts_bytes) + total_size + len(footer)

    header_io = io.BytesIO(bytes(parts_bytes))
    file_io = open(path, "rb")
    footer_io = io.BytesIO(footer)
    bytes_sent = 0

    with Progress(
        TextColumn("[bold green]Uploading", justify="right"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=con,
        transient=False,
    ) as progress_bar:
        task_id = progress_bar.add_task("upload", total=total_size)

        def read_stream(size: int) -> bytes:
            nonlocal bytes_sent
            h = header_io.read(size)
            if h:
                return h
            chunk = file_io.read(size)
            if chunk:
                bytes_sent += len(chunk)
                progress_bar.update(task_id, completed=bytes_sent)
                if progress_callback:
                    progress_callback(bytes_sent, total_size)
                return chunk
            return footer_io.read(size)

        resp_chunks: list[bytes] = []
        c = Curl()
        c.setopt(CurlOpt.URL, UPLOAD_URL.encode("utf-8"))
        c.setopt(CurlOpt.POST, True)
        c.setopt(CurlOpt.POSTFIELDSIZE_LARGE, content_length)
        c.setopt(
            CurlOpt.HTTPHEADER,
            [f"Content-Type: multipart/form-data; boundary={boundary}".encode("utf-8")],
        )
        c.setopt(CurlOpt.READFUNCTION, read_stream)
        c.setopt(
            CurlOpt.WRITEFUNCTION, lambda d: resp_chunks.append(d) or len(d)
        )
        c.setopt(CurlOpt.TIMEOUT, 600)

        try:
            c.perform()
            status_code = c.getinfo(CurlInfo.RESPONSE_CODE)
        except (KeyboardInterrupt, asyncio.CancelledError):
            con.print("\n[yellow]Upload cancelled by user.[/yellow]")
            raise KeyboardInterrupt
        finally:
            c.close()
            file_io.close()

    if status_code != 200:
        raise RuntimeError(f"GoFile upload failed: HTTP {status_code}")

    raw_body = b"".join(resp_chunks).decode("utf-8", errors="ignore")
    res_data = json.loads(raw_body) if raw_body else {}
    if res_data.get("status") != "ok":
        msg = res_data.get("status") or "upload error"
        raise RuntimeError(f"GoFile upload error: {msg}")

    d = res_data["data"]
    download_page = (
        d.get("downloadPage")
        or f"https://gofile.io/d/{d.get('parentFolderCode', d.get('parentFolder', ''))}"
    )
    guest_token = d.get("guestToken")
    logger.info("GoFile upload complete: {}", download_page)

    con.print(f"[bold green][ok] Upload complete:[/bold green] {download_page}")
    return UploadResult(
        download_page=download_page,
        file_id=d.get("fileId", d.get("id", "")),
        filename=d.get("fileName", d.get("name", path.name)),
        parent_folder=d.get("parentFolder", ""),
        guest_token=guest_token,
    )
