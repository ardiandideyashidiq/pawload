from __future__ import annotations

import math
import time
from typing import Any

from loguru import logger

from telegram.client import TelegramClient


def format_size(bytes_val: float) -> str:
    if bytes_val <= 0:
        return "0 B"
    val = float(bytes_val)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.1f} PB"


def format_time(seconds: float) -> str:
    if math.isinf(seconds) or math.isnan(seconds) or seconds < 0:
        return "--:--"
    sec = int(seconds)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def render_bar(completed: int, total: int, length: int = 12) -> str:
    if total <= 0:
        return "-" * length
    fraction = min(1.0, max(0.0, completed / total))
    filled = int(fraction * length)
    return "=" * filled + "-" * (length - filled)


class TelegramProgressReporter:
    """Streams live file upload/download progress to Telegram with rate-limiting."""

    def __init__(
        self,
        title: str,
        client: TelegramClient | None = None,
        chat_id: str | int | None = None,
        thread_id: int | None = None,
        throttle_interval: float | None = None,
        target_name: str | None = None,
    ):
        self.title = title
        self.client = client or TelegramClient()
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.throttle_interval = (
            throttle_interval
            if throttle_interval is not None
            else self.client.config.throttle_interval
        )
        self.target_name = target_name

        self.message_id: int | None = None
        self.completed: int = 0
        self.total: int = 0
        self.start_time: float = time.monotonic()
        self.last_edit_time: float = 0.0
        self.finished: bool = False

    def _build_progress_text(self) -> str:
        percent = (self.completed / self.total * 100) if self.total > 0 else 0.0
        bar = render_bar(self.completed, self.total)

        elapsed = time.monotonic() - self.start_time
        speed = (self.completed / elapsed) if elapsed > 0.5 else 0.0
        eta = (
            ((self.total - self.completed) / speed)
            if speed > 0 and self.total > self.completed
            else 0.0
        )

        lines = [
            f"[transfer] <b>{self.title}</b>",
            f"<code>[{bar}] {percent:.1f}%</code>",
            f"<b>Progress:</b> {format_size(self.completed)} / {format_size(self.total)}",
            f"<b>Speed:</b> {format_size(speed)}/s | <b>ETA:</b> {format_time(eta)}",
        ]
        if self.target_name:
            lines.append(f"<b>Target:</b> {self.target_name}")

        return "\n".join(lines)

    def _maybe_edit(self, force: bool = False) -> None:
        if self.finished:
            return

        now = time.monotonic()
        if not force and (now - self.last_edit_time < self.throttle_interval):
            return

        text = self._build_progress_text()

        try:
            if self.message_id is None:
                # Initial message
                res = self.client.send_message(
                    text=text,
                    chat_id=self.chat_id,
                    thread_id=self.thread_id,
                    parse_mode="HTML",
                )
                self.message_id = res.get("message_id")
                self.last_edit_time = now
            else:
                success = self.client.edit_message(
                    message_id=self.message_id,
                    text=text,
                    chat_id=self.chat_id,
                    parse_mode="HTML",
                )
                if success:
                    self.last_edit_time = now
        except Exception as e:
            logger.debug(f"Telegram progress reporter send/edit failed: {e}")

    def advance(self, delta_bytes: int, total_bytes: int) -> None:
        """Advance progress by delta bytes (for parallel chunk downloads)."""
        self.completed += delta_bytes
        self.total = total_bytes
        self._maybe_edit(force=(self.total > 0 and self.completed >= self.total))

    def update(self, completed_bytes: int, total_bytes: int) -> None:
        """Update progress with absolute completed bytes (for streaming uploads)."""
        self.completed = completed_bytes
        self.total = total_bytes
        self._maybe_edit(force=(self.total > 0 and self.completed >= self.total))

    def finish(
        self,
        success_url: str | None = None,
        error: str | None = None,
        extra_details: dict[str, Any] | None = None,
    ) -> None:
        """Edit message to persistent final status card."""
        if self.finished:
            return
        self.finished = True

        elapsed = time.monotonic() - self.start_time

        if error:
            lines = [
                "[error] <b>Transfer Failed</b>",
                f"<b>Item:</b> {self.title}",
                f"<b>Error:</b> <code>{error}</code>",
                f"<b>Elapsed:</b> {format_time(elapsed)}",
            ]
        else:
            lines = [
                "[ok] <b>Transfer Complete!</b>",
                f"<b>Item:</b> {self.title}",
            ]
            if self.total > 0:
                lines.append(f"<b>Size:</b> {format_size(self.total)}")
            lines.append(f"<b>Elapsed:</b> {format_time(elapsed)}")
            if success_url:
                lines.append(f"<b>Link:</b> {success_url}")

            if extra_details:
                for k, v in extra_details.items():
                    lines.append(f"<b>{k}:</b> {v}")

        final_text = "\n".join(lines)

        try:
            if self.message_id is not None:
                self.client.edit_message(
                    message_id=self.message_id,
                    text=final_text,
                    chat_id=self.chat_id,
                    parse_mode="HTML",
                )
            else:
                self.client.send_message(
                    text=final_text,
                    chat_id=self.chat_id,
                    thread_id=self.thread_id,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.debug(f"Telegram progress reporter finish failed: {e}")


def create_reporter(
    title: str,
    target_name: str | None = None,
    chat_id: str | int | None = None,
    thread_id: int | None = None,
    enabled: bool | None = None,
) -> TelegramProgressReporter | None:
    """Instantiate a TelegramProgressReporter if bot token and chat_id are configured.

    If enabled is None, defaults to True whenever bot credentials are configured.
    If enabled is False, notifications are explicitly suppressed.
    """
    if enabled is False:
        return None
    try:
        client = TelegramClient(chat_id=chat_id, thread_id=thread_id)
        if client.is_configured:
            return TelegramProgressReporter(
                title=title,
                client=client,
                chat_id=chat_id,
                thread_id=thread_id,
                target_name=target_name,
            )
        logger.debug(
            "Telegram progress reporter skipped: bot_token or chat_id not configured."
        )
    except Exception as e:
        logger.debug(f"Could not create Telegram progress reporter: {e}")
    return None
