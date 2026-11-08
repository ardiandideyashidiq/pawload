from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from curl_cffi.requests import AsyncSession
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from gdrive.api import (
    extract_gdrive_id,
    inspect_target_async,
    load_cookies,
    resolve_direct_download,
)
from gdrive.config import Config


@dataclass
class DownloadState:
    url: str
    total_bytes: int
    chunk_size: int
    completed_chunks: list[int] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> DownloadState | None:
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                return cls(
                    url=data["url"],
                    total_bytes=data["total_bytes"],
                    chunk_size=data["chunk_size"],
                    completed_chunks=data.get("completed_chunks", []),
                )
            except Exception:
                return None
        return None

    def save(self, path: Path) -> None:
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {
                        "url": self.url,
                        "total_bytes": self.total_bytes,
                        "chunk_size": self.chunk_size,
                        "completed_chunks": self.completed_chunks,
                    }
                )
            )
            tmp.replace(path)
        except Exception:
            pass


async def download_file_async(
    target: str,
    output_path: str | Path | None = None,
    cookies: dict[str, str] | None = None,
    concurrency: int | None = None,
    chunk_size: int | None = None,
    console: Console | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """
    Download a Google Drive file asynchronously with parallel chunk workers and resume support.
    """
    con = console or Console()
    cfg = Config.load()
    num_workers = concurrency or cfg.concurrency or 4
    c_size = chunk_size or cfg.chunk_size or 8 * 1024 * 1024
    c = cookies if cookies is not None else load_cookies()

    clean_id = extract_gdrive_id(target)

    # 1. Inspect target to see if it's a folder or single file
    info = await inspect_target_async(target, cookies=c)
    if info.is_folder:
        if not info.children:
            raise RuntimeError(f"Google Drive folder '{info.name}' ({info.id}) contains no files.")
        # If folder contains files, pick the first file or single file
        file_item = info.children[0]
        con.print(
            f"[dim]Folder '{info.name}' contains {len(info.children)} file(s). Selecting: {file_item.name}[/dim]"
        )
        clean_id = file_item.id

    # 2. Resolve direct URL, filename, and file size
    direct_url, filename, total_bytes = await resolve_direct_download(clean_id, cookies=c)

    if output_path:
        out_p = Path(output_path)
        if str(output_path).endswith(("/", "\\")) or out_p.is_dir():
            dest = out_p / filename
        else:
            dest = out_p
    else:
        dest = Path(filename)
    dest.parent.mkdir(parents=True, exist_ok=True)

    sidecar_path = Path(f"{dest}.gddownload")

    # If size is unknown, fallback to single stream
    if total_bytes <= 0:
        con.print("[yellow]Single-stream download (size unknown)...[/yellow]")
        try:
            async with AsyncSession(cookies=c) as session:
                resp = await session.get(direct_url, stream=True)
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_content():
                        f.write(chunk)
                        if progress_callback:
                            progress_callback(len(chunk), total_bytes)
        except (KeyboardInterrupt, asyncio.CancelledError):
            con.print("\n[yellow]Download interrupted by user.[/yellow]")
            raise KeyboardInterrupt
        return dest

    # 3. Resume check
    state = DownloadState.load(sidecar_path)
    completed_chunks_set: set[int] = set()
    if state and state.url == direct_url and state.total_bytes == total_bytes:
        completed_chunks_set = set(state.completed_chunks)
        con.print(
            f"[green]Resuming download ({len(completed_chunks_set)} chunks completed)[/green]"
        )
        dest_file = open(dest, "r+b")
    else:
        dest_file = open(dest, "wb")
        dest_file.truncate(total_bytes)
        state = DownloadState(url=direct_url, total_bytes=total_bytes, chunk_size=c_size)

    # 4. Prepare chunks
    chunks: list[tuple[int, int, int]] = []
    num_chunks = (total_bytes + c_size - 1) // c_size
    for i in range(num_chunks):
        start = i * c_size
        end = min((i + 1) * c_size - 1, total_bytes - 1)
        chunks.append((i, start, end))

    write_lock = asyncio.Lock()
    state_lock = asyncio.Lock()
    queue: asyncio.Queue[tuple[int, int, int]] = asyncio.Queue()

    already_done_bytes = 0
    for i, start, end in chunks:
        if i in completed_chunks_set:
            already_done_bytes += end - start + 1
        else:
            queue.put_nowait((i, start, end))

    with Progress(
        TextColumn("[bold blue]{task.fields[name]}", justify="right"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=con,
        transient=False,
    ) as progress:
        overall_task = progress.add_task(
            "Overall",
            total=total_bytes,
            completed=already_done_bytes,
            name="Overall",
        )
        worker_tasks = [
            progress.add_task(
                f"Worker {w + 1}",
                total=0,
                completed=0,
                visible=False,
                name=f"Worker {w + 1}",
            )
            for w in range(num_workers)
        ]

        async def worker(worker_id: int) -> None:
            w_task = worker_tasks[worker_id]
            async with AsyncSession(cookies=c) as session:
                while True:
                    try:
                        chunk_idx, start, end = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    chunk_len = end - start + 1
                    progress.update(w_task, total=chunk_len, completed=0, visible=True)
                    headers = {"Range": f"bytes={start}-{end}"}

                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            resp = await session.get(direct_url, headers=headers, stream=True)
                            if resp.status_code not in (200, 206):
                                raise RuntimeError(f"HTTP {resp.status_code}")

                            current_offset = start
                            async for block in resp.aiter_content():
                                if not block:
                                    continue
                                async with write_lock:
                                    dest_file.seek(current_offset)
                                    dest_file.write(block)
                                current_offset += len(block)
                                progress.update(w_task, advance=len(block))
                                progress.update(overall_task, advance=len(block))
                                if progress_callback:
                                    progress_callback(len(block), total_bytes)

                            async with state_lock:
                                state.completed_chunks.append(chunk_idx)
                                state.save(sidecar_path)

                            progress.update(w_task, visible=False)
                            queue.task_done()
                            break
                        except Exception as e:
                            if attempt == max_retries - 1:
                                progress.update(w_task, visible=False)
                                queue.task_done()
                                con.print(
                                    f"[red]Worker {worker_id + 1} failed chunk {chunk_idx}: {e}[/red]"
                                )
                                raise
                            await asyncio.sleep(1.0)

        tasks = [asyncio.create_task(worker(w)) for w in range(num_workers)]
        try:
            await asyncio.gather(*tasks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            async with state_lock:
                state.save(sidecar_path)
            con.print("\n[yellow]Download paused. Progress saved for resume.[/yellow]")
            raise KeyboardInterrupt
        except Exception:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        finally:
            dest_file.flush()
            dest_file.close()

    if sidecar_path.is_file():
        try:
            sidecar_path.unlink()
        except OSError:
            pass

    return dest
