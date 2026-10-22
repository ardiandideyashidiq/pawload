from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sourceforge.config import (
    get_unified_config_file,
    load_section,
    save_section,
)

CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sourceforge"
)
CONFIG_FILE = get_unified_config_file()
LEGACY_CONFIG_FILE = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    / "telegram"
    / "config.toml"
)


@dataclass
class Config:
    bot_token: str | None = None
    chat_id: str | None = None
    thread_id: int | None = None
    throttle_interval: float = 2.0
    parse_mode: str = "HTML"

    @classmethod
    def load(cls) -> Config:
        data = load_section(
            "telegram", config_file=CONFIG_FILE, legacy_file=LEGACY_CONFIG_FILE
        )

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
        save_section(
            "telegram",
            {
                "bot_token": self.bot_token,
                "chat_id": self.chat_id,
                "thread_id": self.thread_id,
                "throttle_interval": self.throttle_interval,
                "parse_mode": self.parse_mode,
            },
            config_file=CONFIG_FILE,
        )


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
