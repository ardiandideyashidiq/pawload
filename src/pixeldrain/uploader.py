from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from curl_cffi import requests
from curl_cffi.curl import CurlMime
from rich.console import Console

from pixeldrain.api import API_BASE, get_auth_headers


@dataclass
class UploadResult:
    id: str
    url: str
    name: str
    size: int


def upload_file(
    file_path: str | Path,
    api_key: str | None = None,
    console: Console | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> UploadResult:
    con = console or Console()
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Local file not found: {path}")

    total_size = path.stat().st_size
    url = f"{API_BASE}/file"
    headers = get_auth_headers(api_key)

    mp = CurlMime()
    mp.addpart(name="file", filename=path.name, local_path=str(path))

    with con.status(
        f"[cyan]Uploading {path.name} to Pixeldrain ({total_size} bytes)...[/cyan]"
    ):
        try:
            resp = requests.post(
                url,
                headers=headers,
                multipart=mp,
                timeout=300,
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            con.print("\n[yellow]Upload cancelled by user.[/yellow]")
            raise KeyboardInterrupt
        finally:
            mp.close()

    if resp.status_code != 201 and resp.status_code != 200:
        data = resp.json() if resp.content else {}
        msg = data.get("message") or f"HTTP {resp.status_code}"
        raise RuntimeError(f"Pixeldrain upload failed: {msg}")

    res_data = resp.json()
    if not res_data.get("success", False) or "id" not in res_data:
        err = res_data.get("message") or "Upload unsuccessful"
        raise RuntimeError(f"Pixeldrain upload error: {err}")

    file_id = res_data["id"]
    share_url = f"https://pixeldrain.com/u/{file_id}"
    con.print(f"[bold green][ok] Upload complete:[/bold green] {share_url}")
    return UploadResult(
        id=file_id,
        url=share_url,
        name=path.name,
        size=total_size,
    )
