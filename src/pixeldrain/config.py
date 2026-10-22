from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pixeldrain"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class Config:
    api_key: str | None = None
    concurrency: int = 4
    chunk_size: int = 8 * 1024 * 1024

    @classmethod
    def load(cls) -> Config:
        data: dict = {}
        if CONFIG_FILE.is_file():
            try:
                with open(CONFIG_FILE, "rb") as f:
                    data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError):
                pass

        api_key = (
            os.environ.get("PIXELDRAIN_API_KEY")
            or os.environ.get("PIXELDRAIN_KEY")
            or data.get("api_key")
        )
        concurrency = int(os.environ.get("PIXELDRAIN_CONCURRENCY", data.get("concurrency", 4)))
        chunk_size = int(os.environ.get("PIXELDRAIN_CHUNK_SIZE", data.get("chunk_size", 8 * 1024 * 1024)))

        return cls(
            api_key=api_key,
            concurrency=concurrency,
            chunk_size=chunk_size,
        )

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = []
        if self.api_key:
            lines.append(f'api_key = "{self.api_key}"')
        lines.append(f"concurrency = {self.concurrency}")
        lines.append(f"chunk_size = {self.chunk_size}")

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def format_size(bytes_val: int) -> str:
    if bytes_val <= 0:
        return "0 B"
    val = float(bytes_val)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.1f} PB"


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
