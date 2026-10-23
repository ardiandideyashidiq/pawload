from __future__ import annotations

import asyncio
import os
import platform
import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from gofile.api import get_content, get_content_id, parse_content_items
from gofile.client import GoFileClient
from pixeldrain.client import PixelDrainClient
from sourceforge.client import SourceForgeClient
from sourceforge.config import get_unified_config_file, load_all_sections, save_section
from sourceforge.mirrors import fetch_live_mirrors, parse_target
from telegram.client import TelegramClient
from telegram.reporter import TelegramProgressReporter
from vikingfile.client import VikingFileClient


def get_lan_ip() -> str:
    """Detect local area network IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


class AsyncLoopThread:
    """Dedicated background thread running an asyncio event loop for transfer tasks."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run, daemon=True, name="TransferLoopThread"
        )
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro: Any) -> asyncio.Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


class WebBridge:
    """Backend business bridge managing transfers, config, and live SSE subscribers."""

    def __init__(self) -> None:
        self._worker = AsyncLoopThread()
        self._transfers: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, asyncio.Future] = {}
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._lock = threading.RLock()

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def dispatch_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event payload to all SSE subscribers."""
        payload = {"type": event_type, **data}
        with self._lock:
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(payload)
            except Exception as e:
                logger.debug(f"Subscriber dispatch error: {e}")

    # --- Configuration APIs ---

    def get_active_config(self) -> dict[str, Any]:
        """Return the current unified configuration file path and all sections."""
        cfg_file = get_unified_config_file()
        sections = load_all_sections(cfg_file)
        # Return both flat sections and nested shape for backward and GUI compatibility
        payload = dict(sections)
        payload["path"] = str(cfg_file)
        payload["config_path"] = str(cfg_file)
        payload["config"] = sections
        return payload

    def save_config_section(self, section: str, data: dict[str, Any]) -> bool:
        """Save a specific configuration section atomically to unified config.toml."""
        try:
            save_section(section, data, config_file=get_unified_config_file())
            return True
        except Exception as e:
            logger.error(f"Error saving config section '{section}': {e}")
            return False
    # --- Target Inspection & Metadata ---

    def inspect_target(self, target: str) -> dict[str, Any]:
        """Detect provider and resolve file metadata (name, size, mirrors, hash)."""
        target = target.strip()
        if not target:
            return {"error": "Empty target URL or path"}

        # 1. Local file path check
        local_path = Path(target).expanduser()
        if local_path.is_file():
            return {
                "provider": "local",
                "name": local_path.name,
                "size": local_path.stat().st_size,
                "path": str(local_path.resolve()),
            }

        # 2. GoFile check
        if "gofile.io" in target or target.startswith("gf:"):
            try:
                content_id = get_content_id(target)
                gf_client = GoFileClient()
                token = gf_client.ensure_token()
                content = get_content(content_id=content_id, token=token)
                items = parse_content_items(content)
                if items:
                    it = items[0]
                    return {
                        "provider": "gofile",
                        "name": it.name,
                        "size": it.size,
                        "md5": it.md5,
                        "is_folder": len(items) > 1 or it.is_dir,
                        "content_id": content_id,
                    }
            except Exception as e:
                logger.debug(f"GoFile inspect error: {e}")
                return {"provider": "gofile", "name": target, "error": str(e)}

        # 3. VikingFile check
        if (
            "vik1ngfile.com" in target
            or "vikingfile.com" in target
            or target.startswith("vf:")
        ):
            try:
                vf_client = VikingFileClient()
                item = vf_client.check(target)
                if item:
                    return {
                        "provider": "vikingfile",
                        "name": item.name,
                        "size": item.size,
                        "hash": item.hash,
                    }
            except Exception as e:
                logger.debug(f"VikingFile inspect error: {e}")
                return {"provider": "vikingfile", "name": target, "error": str(e)}

        # 4. Pixeldrain check
        if "pixeldrain.com" in target or target.startswith("pd:"):
            try:
                pd_client = PixelDrainClient()
                p_item = pd_client.info(target)
                if p_item:
                    return {
                        "provider": "pixeldrain",
                        "name": p_item.name,
                        "size": p_item.size,
                        "sha256": getattr(p_item, "sha256", None),
                    }
            except Exception as e:
                logger.debug(f"Pixeldrain inspect error: {e}")
                return {"provider": "pixeldrain", "name": target, "error": str(e)}

        # 5. SourceForge check
        if (
            "sourceforge.net" in target
            or "fsdn.com" in target
            or target.startswith("sf:")
            or ("/" in target and not target.startswith(("http://", "https://")))
        ):
            try:
                target_info = parse_target(target)
                mirror_names = ["autoselect"]
                if target_info.remote_path:
                    live_mirrors = fetch_live_mirrors(
                        target_info.project, target_info.remote_path
                    )
                    if live_mirrors:
                        mirror_names = [m.id for m in live_mirrors]
                return {
                    "provider": "sourceforge",
                    "project": target_info.project,
                    "remote_path": target_info.remote_path,
                    "name": Path(target_info.remote_path).name
                    if target_info.remote_path
                    else target_info.project,
                    "mirrors": mirror_names,
                    "md5": target_info.expected_md5,
                }
            except Exception as e:
                logger.debug(f"SourceForge inspect error: {e}")
                return {"provider": "sourceforge", "name": target, "error": str(e)}

        return {"provider": "unknown", "name": target}

    def open_path(self, path_str: str) -> bool:
        """Open local file or folder in default OS desktop environment."""
        target = Path(path_str).expanduser()
        if not target.exists():
            return False

        try:
            current_os = platform.system()
            if current_os == "Windows":
                os.startfile(str(target))
            elif current_os == "Darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
            return True
        except Exception as e:
            logger.error(f"Failed to open path '{path_str}': {e}")
            return False

    # --- Transfer Queue & Operations ---

    def get_transfers(self) -> list[dict[str, Any]]:
        """Return all tracked transfers."""
        with self._lock:
            return list(self._transfers.values())

    def start_download(
        self,
        target: str,
        output_dir: str | None = None,
        concurrency: int = 4,
        mirror: str | None = None,
        notify: bool = False,
    ) -> str:
        """Initiate background download with real-time SSE streaming."""
        transfer_id = f"dl_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        info = self.inspect_target(target)
        provider = info.get("provider", "unknown")
        filename = info.get("name") or Path(target).name or "download.bin"

        dest_dir = Path(output_dir).expanduser() if output_dir else Path.cwd()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / filename

        transfer_record: dict[str, Any] = {
            "id": transfer_id,
            "type": "download",
            "provider": provider,
            "target": target,
            "name": filename,
            "dest_path": str(dest_file),
            "status": "running",
            "total_bytes": info.get("size") or 0,
            "completed_bytes": 0,
            "speed_bps": 0,
            "eta_seconds": 0,
            "progress_percent": 0.0,
            "concurrency": concurrency,
            "mirror": mirror,
            "notify": notify,
            "error": None,
            "started_at": time.time(),
        }

        with self._lock:
            self._transfers[transfer_id] = transfer_record

        self.dispatch_event("transfer_added", transfer_record)

        coro = self._run_download_task(
            transfer_id, target, provider, dest_file, concurrency, mirror, notify
        )
        future = self._worker.submit(coro)
        with self._lock:
            self._futures[transfer_id] = future

        return transfer_id

    async def _run_download_task(
        self,
        transfer_id: str,
        target: str,
        provider: str,
        dest_file: Path,
        concurrency: int,
        mirror: str | None,
        notify: bool,
    ) -> None:
        last_time = time.time()
        last_bytes = 0
        reporter: TelegramProgressReporter | None = None

        if notify:
            try:
                tg_client = TelegramClient()
                if tg_client.is_configured:
                    reporter = TelegramProgressReporter(
                        title=f"[download] {dest_file.name}",
                        client=tg_client,
                        target_name=dest_file.name,
                    )
            except Exception as e:
                logger.debug(f"Failed to initialize Telegram reporter: {e}")

        def progress_cb(completed: int, total: int) -> None:
            nonlocal last_time, last_bytes
            now = time.time()
            elapsed = now - last_time
            speed = 0.0
            if elapsed >= 0.5:
                delta = completed - last_bytes
                speed = max(0.0, delta / elapsed)
                last_time = now
                last_bytes = completed

            eta = (
                (total - completed) / speed
                if (speed > 0 and total > completed)
                else 0.0
            )
            percent = (completed / total * 100.0) if total > 0 else 0.0

            with self._lock:
                rec = self._transfers.get(transfer_id)
                if rec and rec["status"] == "running":
                    rec["completed_bytes"] = completed
                    rec["total_bytes"] = total
                    rec["speed_bps"] = speed
                    rec["eta_seconds"] = eta
                    rec["progress_percent"] = percent

            self.dispatch_event(
                "transfer_progress",
                {
                    "id": transfer_id,
                    "completed_bytes": completed,
                    "total_bytes": total,
                    "speed_bps": speed,
                    "eta_seconds": eta,
                    "progress_percent": percent,
                },
            )

            if reporter:
                reporter.update(completed, total)

        try:
            if provider == "sourceforge":
                sf = SourceForgeClient()
                await sf.download_async(
                    target=target,
                    output_path=dest_file,
                    mirror=mirror,
                    concurrency=concurrency,
                    interactive_prompt=False,
                    progress_callback=progress_cb,
                )
            elif provider == "gofile":
                gf = GoFileClient()
                await gf.download_async(
                    target=target,
                    output_path=dest_file,
                    concurrency=concurrency,
                    interactive=False,
                    progress_callback=progress_cb,
                )
            elif provider == "vikingfile":
                vf = VikingFileClient()
                await vf.download_async(
                    target=target,
                    output_path=dest_file,
                    concurrency=concurrency,
                    progress_callback=progress_cb,
                )
            elif provider == "pixeldrain":
                pd = PixelDrainClient()
                await pd.download_async(
                    target=target,
                    output_path=dest_file,
                    concurrency=concurrency,
                    progress_callback=progress_cb,
                )
            else:
                sf = SourceForgeClient()
                await sf.download_async(
                    target=target,
                    output_path=dest_file,
                    mirror=mirror,
                    concurrency=concurrency,
                    interactive_prompt=False,
                    progress_callback=progress_cb,
                )

            with self._lock:
                rec = self._transfers.get(transfer_id)
                if rec and rec["status"] == "running":
                    rec["status"] = "completed"
                    rec["progress_percent"] = 100.0
                    rec["speed_bps"] = 0
                    rec["eta_seconds"] = 0
                snapshot = (
                    dict(rec) if rec else {"id": transfer_id, "status": "completed"}
                )

            if reporter:
                reporter.finish(success=True)

            self.dispatch_event("transfer_completed", snapshot)

        except asyncio.CancelledError:
            with self._lock:
                rec = self._transfers.get(transfer_id)
                if rec and rec["status"] == "running":
                    rec["status"] = "paused"
                    rec["speed_bps"] = 0
                    rec["eta_seconds"] = 0
                snapshot = dict(rec) if rec else {"id": transfer_id, "status": "paused"}
            if reporter:
                reporter.finish(success=False, error_msg="Paused by user")
            self.dispatch_event("transfer_paused", snapshot)

        except Exception as e:
            logger.error(f"Transfer error for {transfer_id}: {e}")
            with self._lock:
                rec = self._transfers.get(transfer_id)
                if rec:
                    rec["status"] = "error"
                    rec["error"] = str(e)
                    rec["speed_bps"] = 0
                    rec["eta_seconds"] = 0
                snapshot = (
                    dict(rec)
                    if rec
                    else {"id": transfer_id, "status": "error", "error": str(e)}
                )
            if reporter:
                reporter.finish(success=False, error_msg=str(e))
            self.dispatch_event("transfer_error", snapshot)

    def start_upload(
        self,
        local_path: str,
        provider: str,
        remote_path: str = "",
        notify: bool = False,
    ) -> str:
        """Initiate background upload with progress reporting."""
        file_path = Path(local_path).expanduser()
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {local_path}")

        transfer_id = f"ul_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        total_size = file_path.stat().st_size

        transfer_record: dict[str, Any] = {
            "id": transfer_id,
            "type": "upload",
            "provider": provider,
            "target": str(file_path),
            "name": file_path.name,
            "dest_path": remote_path,
            "status": "running",
            "total_bytes": total_size,
            "completed_bytes": 0,
            "speed_bps": 0,
            "eta_seconds": 0,
            "progress_percent": 0.0,
            "notify": notify,
            "error": None,
            "started_at": time.time(),
        }

        with self._lock:
            self._transfers[transfer_id] = transfer_record

        self.dispatch_event("transfer_added", transfer_record)

        coro = self._run_upload_task(
            transfer_id, file_path, provider, remote_path, notify
        )
        future = self._worker.submit(coro)
        with self._lock:
            self._futures[transfer_id] = future

        return transfer_id

    async def _run_upload_task(
        self,
        transfer_id: str,
        file_path: Path,
        provider: str,
        remote_path: str,
        notify: bool,
    ) -> None:
        reporter: TelegramProgressReporter | None = None
        if notify:
            try:
                tg_client = TelegramClient()
                if tg_client.is_configured:
                    reporter = TelegramProgressReporter(
                        title=f"[upload] {file_path.name}",
                        client=tg_client,
                        target_name=file_path.name,
                    )
            except Exception as e:
                logger.debug(f"Failed to initialize Telegram reporter: {e}")

        last_time = time.time()
        last_bytes = 0

        def progress_cb(completed: int, total: int) -> None:
            nonlocal last_time, last_bytes
            now = time.time()
            dt = now - last_time
            if dt >= 0.25 or completed == total:
                speed = (completed - last_bytes) / dt if dt > 0 else 0
                eta = (total - completed) / speed if speed > 0 else 0
                percent = (completed / total * 100) if total > 0 else 0.0

                with self._lock:
                    rec = self._transfers.get(transfer_id)
                    if rec:
                        rec["completed_bytes"] = completed
                        rec["total_bytes"] = total
                        rec["speed_bps"] = speed
                        rec["eta_seconds"] = eta
                        rec["progress_percent"] = percent
                        self.dispatch_event("transfer_progress", dict(rec))

                if reporter:
                    reporter.update(completed, total)

                last_time = now
                last_bytes = completed

        try:
            result_url = ""
            if provider == "gofile":
                gf = GoFileClient()
                res = await gf.upload_async(
                    file_path=file_path,
                    folder_id=remote_path or None,
                    progress_callback=progress_cb,
                )
                result_url = res.download_page or ""
            elif provider == "vikingfile":
                vf = VikingFileClient()
                vres = await vf.upload_async(
                    file_path=file_path,
                    remote_path=remote_path,
                    progress_callback=progress_cb,
                )
                result_url = vres.download_url or ""
            elif provider == "pixeldrain":
                pd = PixelDrainClient()
                pres = await pd.upload_async(file_path=file_path)
                result_url = pres.url or ""
            elif provider == "sourceforge":
                sf = SourceForgeClient()
                await sf.upload_async(
                    local_path=file_path,
                    remote_dir=remote_path,
                    interactive_prompt=False,
                    progress_callback=progress_cb,
                )
                result_url = f"https://sourceforge.net/projects/{sf.project}/files/{file_path.name}"
            else:
                raise ValueError(f"Unknown upload provider: {provider}")

            with self._lock:
                rec = self._transfers.get(transfer_id)
                if rec:
                    rec["status"] = "completed"
                    rec["result_url"] = result_url
                    rec["progress_percent"] = 100.0
                    rec["speed_bps"] = 0
                    rec["eta_seconds"] = 0
                snapshot = (
                    dict(rec) if rec else {"id": transfer_id, "status": "completed"}
                )

            if reporter:
                reporter.finish(success=True)

            self.dispatch_event("transfer_completed", snapshot)

        except asyncio.CancelledError:
            with self._lock:
                rec = self._transfers.get(transfer_id)
                if rec:
                    rec["status"] = "cancelled"
                    rec["speed_bps"] = 0
                    rec["eta_seconds"] = 0
                snapshot = (
                    dict(rec) if rec else {"id": transfer_id, "status": "cancelled"}
                )
            if reporter:
                reporter.finish(success=False, error_msg="Cancelled by user")
            self.dispatch_event("transfer_cancelled", snapshot)

        except Exception as e:
            logger.error(f"Upload error for {transfer_id}: {e}")
            with self._lock:
                rec = self._transfers.get(transfer_id)
                if rec:
                    rec["status"] = "error"
                    rec["error"] = str(e)
                    rec["speed_bps"] = 0
                    rec["eta_seconds"] = 0
                snapshot = (
                    dict(rec)
                    if rec
                    else {"id": transfer_id, "status": "error", "error": str(e)}
                )
            if reporter:
                reporter.finish(success=False, error_msg=str(e))
            self.dispatch_event("transfer_error", snapshot)

    def pause_transfer(self, transfer_id: str) -> bool:
        """Pause an in-flight transfer cleanly."""
        with self._lock:
            fut = self._futures.get(transfer_id)
            rec = self._transfers.get(transfer_id)
            if fut and not fut.done():
                fut.cancel()
            if rec and rec["status"] == "running":
                rec["speed_bps"] = 0
                rec["eta_seconds"] = 0
                self.dispatch_event("transfer_paused", dict(rec))
                return True
        return False

    def resume_transfer(self, transfer_id: str) -> bool:
        """Resume a paused transfer from where it left off."""
        with self._lock:
            rec = self._transfers.get(transfer_id)
        if not rec or rec["status"] != "paused":
            return False

        if rec["type"] == "download":
            coro = self._run_download_task(
                transfer_id=transfer_id,
                target=rec["target"],
                provider=rec["provider"],
                dest_file=Path(rec["dest_path"]),
                concurrency=rec["concurrency"],
                mirror=rec.get("mirror"),
                notify=rec.get("notify", False),
            )
            rec["status"] = "running"
            snapshot = dict(rec)
            future = self._worker.submit(coro)
            with self._lock:
                self._futures[transfer_id] = future
            self.dispatch_event("transfer_resumed", snapshot)
            return True
        return False

    def cancel_transfer(self, transfer_id: str) -> bool:
        """Cancel an in-flight transfer and terminate tasks."""
        with self._lock:
            fut = self._futures.get(transfer_id)
            rec = self._transfers.get(transfer_id)
            if fut and not fut.done():
                fut.cancel()
            if rec:
                rec["status"] = "cancelled"
                rec["speed_bps"] = 0
                rec["eta_seconds"] = 0
                self.dispatch_event("transfer_cancelled", dict(rec))
                return True
        return False
