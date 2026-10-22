from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "telegram"
)
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class Config:
    bot_token: str | None = None
    chat_id: str | None = None
    thread_id: int | None = None
    throttle_interval: float = 2.0
    parse_mode: str = "HTML"

    @classmethod
    def load(cls) -> Config:
        data: dict = {}
        if CONFIG_FILE.is_file():
            try:
                with open(CONFIG_FILE, "rb") as f:
                    data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError):
                pass

        bot_token = (
            os.environ.get("TELEGRAM_BOT_TOKEN")
            or os.environ.get("TG_BOT_TOKEN")
            or data.get("bot_token")
        )
        chat_id = (
            os.environ.get("TELEGRAM_CHAT_ID")
            or os.environ.get("TG_CHAT_ID")
            or (str(data.get("chat_id")) if data.get("chat_id") is not None else None)
        )
        raw_thread = os.environ.get("TELEGRAM_THREAD_ID", data.get("thread_id"))
        thread_id = int(raw_thread) if raw_thread is not None else None

        throttle = float(
            os.environ.get(
                "TELEGRAM_THROTTLE_INTERVAL", data.get("throttle_interval", 2.0)
            )
        )
        parse_mode = os.environ.get(
            "TELEGRAM_PARSE_MODE", data.get("parse_mode", "HTML")
        )

        return cls(
            bot_token=bot_token,
            chat_id=chat_id,
            thread_id=thread_id,
            throttle_interval=throttle,
            parse_mode=parse_mode,
        )

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = []
        if self.bot_token:
            lines.append(f'bot_token = "{self.bot_token}"')
        if self.chat_id:
            lines.append(f'chat_id = "{self.chat_id}"')
        if self.thread_id is not None:
            lines.append(f"thread_id = {self.thread_id}")
        lines.append(f"throttle_interval = {self.throttle_interval}")
        lines.append(f'parse_mode = "{self.parse_mode}"')

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def setup_logging(verbose: int = 0) -> None:
    import sys

    from loguru import logger

    logger.remove()
    if verbose == 0:
        logger.add(
            sys.stderr,
            level="WARNING",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )
    elif verbose == 1:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )
    else:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss}</green> | <cyan>{name}:{line}</cyan> | <level>{level: <8}</level> | <level>{message}</level>",
        )
