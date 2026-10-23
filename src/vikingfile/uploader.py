from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from curl_cffi import requests
from curl_cffi.curl import CurlMime
from rich.console import Console

from vikingfile.api import get_upload_server


@dataclass
class UploadResult:
    name: str
    size: int
    hash: str
    url: str


def upload_file(
    file_path: str | Path,
    user: str = "",
    remote_path: str = "",
    console: Console | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> UploadResult:
    con = console or Console()
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Local file not found: {path}")

    total_size = path.stat().st_size
    upload_server = get_upload_server()

    mp = CurlMime()
    mp.addpart(name="user", data=user.encode())
    if remote_path:
        mp.addpart(name="path", data=remote_path.encode())
    mp.addpart(name="file", filename=path.name, local_path=str(path))

    with con.status(
        f"[cyan]Uploading {path.name} to Vikingfile ({total_size} bytes)...[/cyan]"
    ):
        try:
            resp = requests.post(
                upload_server,
                multipart=mp,
                timeout=300,
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            con.print("\n[yellow]Upload cancelled by user.[/yellow]")
            raise KeyboardInterrupt
        finally:
            mp.close()

    if resp.status_code != 200:
        raise RuntimeError(f"Vikingfile upload failed: HTTP {resp.status_code}")

    res_data = resp.json()
    if "hash" not in res_data:
        err = res_data.get("error") or "upload error"
        raise RuntimeError(f"Vikingfile upload error: {err}")

    result = UploadResult(
        name=res_data.get("name", path.name),
        size=int(res_data.get("size", total_size)),
        hash=res_data["hash"],
        url=res_data.get("url") or f"https://vikingfile.com/f/{res_data['hash']}",
    )
    con.print(f"[bold green][ok] Upload complete:[/bold green] {result.url}")
    return result
