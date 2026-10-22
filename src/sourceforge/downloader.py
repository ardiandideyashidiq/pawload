from __future__ import annotations

import asyncio
import hashlib
import json
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from curl_cffi.requests import AsyncSession
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

from sourceforge.mirrors import resolve_download_target


def get_expected_md5(project: str, remote_path: str) -> str | None:
    """Fetch expected MD5 checksum from SourceForge RSS feed."""
    clean_path = remote_path.strip().lstrip("/")
    parts = clean_path.split("/")
    remote_dir = "/".join(parts[:-1]) if len(parts) > 1 else ""
    target_name = parts[-1]

    rss_url = f"https://sourceforge.net/projects/{project}/rss?path=/{remote_dir}"
    try:
        from curl_cffi import requests

        resp = requests.get(rss_url, timeout=10)
        if resp.status_code != 200:
            return None
        root = ET.fromstring(resp.content)
        namespaces = {"media": "http://video.search.yahoo.com/mrss/"}
        for item in root.findall(".//item"):
            title = (item.find("title").text or "").strip()
            if title.endswith(target_name) or title == f"/{clean_path}":
                hash_elem = item.find(".//media:hash", namespaces)
                if hash_elem is not None and hash_elem.text:
                    return hash_elem.text.strip().lower()
    except Exception:
        pass
    return None


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
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
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
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "url": self.url,
                        "total_bytes": self.total_bytes,
                        "chunk_size": self.chunk_size,
                        "completed_chunks": self.completed_chunks,
                    },
                    f,
                )
        except OSError:
            pass


async def download_file_async(
    project: str,
    remote_path: str,
    output_path: str | Path | None = None,
    mirror: str | None = None,
    concurrency: int = 4,
    chunk_size: int = 8 * 1024 * 1024,
    verify_checksum: bool = True,
    expected_md5: str | None = None,
    interactive_prompt: bool = True,
    console: Console | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    con = console or Console()
    logger.info("Resolving download target: {}/{} (mirror={})", project, remote_path, mirror or "auto")
    target = resolve_download_target(
        project=project,
        remote_path=remote_path,
        mirror=mirror,
        interactive_prompt=interactive_prompt,
        console=con,
    )
    logger.info("Target URL resolved: {} (size={} bytes, ranges={})", target.direct_url, target.content_length, target.accept_ranges)

    dest = Path(output_path) if output_path else Path(target.filename)
    if dest.is_dir():
        dest = dest / target.filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    sidecar_path = Path(f"{dest}.sfdownload")
    total_bytes = target.content_length

    # Fallback to single stream if server does not accept ranges or total size is unknown
    if not target.accept_ranges or total_bytes <= 0:
        con.print("[yellow]Server does not support range requests; using single stream.[/yellow]")
        try:
            async with AsyncSession() as session:
                resp = await session.get(target.direct_url, stream=True)
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_content():
                        f.write(chunk)
                        if progress_callback:
                            progress_callback(len(chunk), total_bytes)
        except (KeyboardInterrupt, asyncio.CancelledError):
            con.print("\n[yellow]Download interrupted by user.[/yellow]")
            raise KeyboardInterrupt
        return dest

    # Multi-part parallel download with resume
    state = DownloadState.load(sidecar_path)
    completed_chunks_set = set()
    if state and state.url == target.direct_url and state.total_bytes == total_bytes:
        completed_chunks_set = set(state.completed_chunks)
        con.print(f"[green]Resuming download ({len(completed_chunks_set)} chunks completed)[/green]")
        dest_file = open(dest, "r+b")
    else:
        dest_file = open(dest, "wb")
        dest_file.truncate(total_bytes)
        state = DownloadState(url=target.direct_url, total_bytes=total_bytes, chunk_size=chunk_size)

    # Compute chunk slices
    chunks: list[tuple[int, int, int]] = []
    num_chunks = (total_bytes + chunk_size - 1) // chunk_size
    for i in range(num_chunks):
        start = i * chunk_size
        end = min((i + 1) * chunk_size - 1, total_bytes - 1)
        chunks.append((i, start, end))

    write_lock = asyncio.Lock()
    state_lock = asyncio.Lock()
    queue: asyncio.Queue[tuple[int, int, int]] = asyncio.Queue()

    already_done_bytes = 0
    for i, start, end in chunks:
        if i in completed_chunks_set:
            already_done_bytes += (end - start + 1)
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
            progress.add_task(f"Worker {w+1}", total=0, completed=0, visible=False, name=f"Worker {w+1}")
            for w in range(concurrency)
        ]

        async def worker(worker_id: int) -> None:
            w_task = worker_tasks[worker_id]
            async with AsyncSession() as session:
                while True:
                    try:
                        chunk_idx, start, end = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    chunk_len = end - start + 1
                    logger.debug("Worker {} downloading chunk {}: bytes {}-{}", worker_id + 1, chunk_idx, start, end)
                    progress.update(w_task, total=chunk_len, completed=0, visible=True)

                    headers = {"Range": f"bytes={start}-{end}"}

                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            resp = await session.get(target.direct_url, headers=headers, stream=True)
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

                            logger.debug("Worker {} completed chunk {}", worker_id + 1, chunk_idx)
                            progress.update(w_task, visible=False)
                            queue.task_done()
                            break
                        except Exception as e:
                            if attempt == max_retries - 1:
                                progress.update(w_task, visible=False)
                                queue.task_done()
                                con.print(f"[red]Worker {worker_id+1} failed chunk {chunk_idx}: {e}[/red]")
                                raise
                            await asyncio.sleep(1.0)

        tasks = [asyncio.create_task(worker(w)) for w in range(concurrency)]
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
        finally:
            dest_file.flush()
            dest_file.close()
    # Clean up sidecar file upon successful completion
    if sidecar_path.is_file():
        try:
            sidecar_path.unlink()
        except OSError:
            pass

    # Verify checksum if enabled
    if verify_checksum:
        try:
            with con.status("[cyan]Verifying MD5 checksum...[/cyan]"):
                md5_to_check = expected_md5 or get_expected_md5(project, remote_path)
                if md5_to_check:
                    logger.info("Verifying MD5 checksum (expected: {})", md5_to_check)
                    hasher = hashlib.md5()
                    with open(dest, "rb") as f:
                        while chunk := f.read(1024 * 1024):
                            hasher.update(chunk)
                    computed_md5 = hasher.hexdigest().lower()
                    if computed_md5 != md5_to_check:
                        raise ValueError(
                            f"Checksum mismatch for {dest.name}! Expected {md5_to_check}, got {computed_md5}"
                        )
                    logger.info("MD5 verified successfully: {}", computed_md5)
                    con.print(f"[bold green]✓ MD5 Verified:[/bold green] {computed_md5}")
                else:
                    con.print("[dim]No remote MD5 checksum found in metadata; skipped hash check.[/dim]")
        except KeyboardInterrupt:
            con.print("\n[yellow]Checksum verification interrupted.[/yellow]")
            raise KeyboardInterrupt
    return dest
