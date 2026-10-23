from __future__ import annotations

import json
from typing import Any

from curl_cffi import requests
from loguru import logger

from telegram.config import Config


class TelegramClient:
    """Unified Telegram Bot API client using curl_cffi."""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | int | None = None,
        thread_id: int | None = None,
        config: Config | None = None,
    ):
        self.config = config or Config.load()
        self.bot_token = bot_token or self.config.bot_token
        self.chat_id = str(chat_id) if chat_id is not None else self.config.chat_id
        self.thread_id = thread_id if thread_id is not None else self.config.thread_id
        self.parse_mode = self.config.parse_mode


    @property
    def is_configured(self) -> bool:
        """Return True if both bot token and chat ID are present."""
        return bool(self.bot_token and self.chat_id)
    def _get_url(self, method: str) -> str:
        if not self.bot_token:
            raise ValueError(
                "Telegram bot token not configured. Set TELEGRAM_BOT_TOKEN or run 'tg config set'."
            )
        return self.BASE_URL.format(token=self.bot_token, method=method)

    def _resolve_chat(self, chat_id: str | int | None) -> str:
        resolved = str(chat_id) if chat_id is not None else self.chat_id
        if not resolved:
            raise ValueError(
                "Telegram chat_id not specified and not found in config/environment."
            )
        return resolved

    def get_me(self) -> dict[str, Any]:
        """Fetch bot info via getMe."""
        url = self._get_url("getMe")
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(
                f"Telegram API error: {data.get('description', 'Unknown error')}"
            )
        return data.get("result", {})

    async def get_me_async(self) -> dict[str, Any]:
        """Fetch bot info asynchronously via getMe."""
        url = self._get_url("getMe")
        async with requests.AsyncSession() as session:
            resp = await session.get(url, timeout=15)
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(
                    f"Telegram API error: {data.get('description', 'Unknown error')}"
                )
            return data.get("result", {})

    def send_message(
        self,
        text: str,
        chat_id: str | int | None = None,
        thread_id: int | None = None,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
        disable_preview: bool = True,
    ) -> dict[str, Any]:
        """Send message synchronously."""
        url = self._get_url("sendMessage")
        target_chat = self._resolve_chat(chat_id)
        target_thread = thread_id if thread_id is not None else self.thread_id
        target_mode = parse_mode or self.parse_mode

        payload: dict[str, Any] = {
            "chat_id": target_chat,
            "text": text,
            "disable_web_page_preview": disable_preview,
        }
        if target_thread is not None:
            payload["message_thread_id"] = target_thread
        if target_mode:
            payload["parse_mode"] = target_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        resp = requests.post(url, json=payload, timeout=20)
        data = resp.json()
        if not data.get("ok"):
            err = data.get("description", "Unknown error")
            logger.warning(f"Telegram sendMessage failed: {err}")
            raise RuntimeError(f"Telegram API error: {err}")
        return data.get("result", {})

    async def send_message_async(
        self,
        text: str,
        chat_id: str | int | None = None,
        thread_id: int | None = None,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
        disable_preview: bool = True,
    ) -> dict[str, Any]:
        """Send message asynchronously."""
        url = self._get_url("sendMessage")
        target_chat = self._resolve_chat(chat_id)
        target_thread = thread_id if thread_id is not None else self.thread_id
        target_mode = parse_mode or self.parse_mode

        payload: dict[str, Any] = {
            "chat_id": target_chat,
            "text": text,
            "disable_web_page_preview": disable_preview,
        }
        if target_thread is not None:
            payload["message_thread_id"] = target_thread
        if target_mode:
            payload["parse_mode"] = target_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        async with requests.AsyncSession() as session:
            resp = await session.post(url, json=payload, timeout=20)
            data = resp.json()
            if not data.get("ok"):
                err = data.get("description", "Unknown error")
                logger.warning(f"Telegram sendMessage failed: {err}")
                raise RuntimeError(f"Telegram API error: {err}")
            return data.get("result", {})

    def edit_message(
        self,
        message_id: int,
        text: str,
        chat_id: str | int | None = None,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
        disable_preview: bool = True,
    ) -> bool:
        """Edit an existing message synchronously."""
        url = self._get_url("editMessageText")
        target_chat = self._resolve_chat(chat_id)
        target_mode = parse_mode or self.parse_mode

        payload: dict[str, Any] = {
            "chat_id": target_chat,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": disable_preview,
        }
        if target_mode:
            payload["parse_mode"] = target_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        resp = requests.post(url, json=payload, timeout=20)
        data = resp.json()
        if not data.get("ok"):
            err = str(data.get("description", ""))
            if "message is not modified" in err:
                return True
            logger.debug(f"Telegram editMessage failed: {err}")
            return False
        return True

    async def edit_message_async(
        self,
        message_id: int,
        text: str,
        chat_id: str | int | None = None,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
        disable_preview: bool = True,
    ) -> bool:
        """Edit an existing message asynchronously."""
        url = self._get_url("editMessageText")
        target_chat = self._resolve_chat(chat_id)
        target_mode = parse_mode or self.parse_mode

        payload: dict[str, Any] = {
            "chat_id": target_chat,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": disable_preview,
        }
        if target_mode:
            payload["parse_mode"] = target_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        async with requests.AsyncSession() as session:
            resp = await session.post(url, json=payload, timeout=20)
            data = resp.json()
            if not data.get("ok"):
                err = str(data.get("description", ""))
                if "message is not modified" in err:
                    return True
                logger.debug(f"Telegram editMessage failed: {err}")
                return False
            return True

    def delete_message(self, message_id: int, chat_id: str | int | None = None) -> bool:
        """Delete a message."""
        url = self._get_url("deleteMessage")
        target_chat = self._resolve_chat(chat_id)
        resp = requests.post(
            url, json={"chat_id": target_chat, "message_id": message_id}, timeout=15
        )
        return bool(resp.json().get("ok"))
