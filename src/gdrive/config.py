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
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pawload"
)
CONFIG_FILE = get_unified_config_file()


def find_default_cookie_file() -> Path | None:
    """Find default cookies file location if available."""
    candidates = [
        Path("cookie.txt"),
        Path("cookies.txt"),
        CONFIG_DIR / "cookie.txt",
        CONFIG_DIR / "cookies.txt",
        Path.home() / ".config" / "gdrive" / "cookies.txt",
    ]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return None


@dataclass
class Config:
    cookie_file: str = ""
    concurrency: int = 4
    chunk_size: int = 8 * 1024 * 1024

    @classmethod
    def load(cls) -> Config:
        data = load_section("gdrive", config_file=CONFIG_FILE)
        default_cookie = ""
        found = find_default_cookie_file()
        if found:
            default_cookie = str(found)

        return cls(
            cookie_file=data.get("cookie_file", default_cookie),
            concurrency=int(data.get("concurrency", 4)),
            chunk_size=int(data.get("chunk_size", 8 * 1024 * 1024)),
        )

    def save(self) -> None:
        save_section(
            "gdrive",
            {
                "cookie_file": self.cookie_file,
                "concurrency": self.concurrency,
                "chunk_size": self.chunk_size,
            },
            config_file=CONFIG_FILE,
        )


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
    if verbose == 1:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        )
    elif verbose >= 2:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        )
