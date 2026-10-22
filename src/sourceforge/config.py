from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sourceforge"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class Config:
    username: str | None = None
    project: str | None = None
    key_path: str | None = None
    password: str | None = None
    default_mirror: str | None = None
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

        username = os.environ.get("SF_USERNAME") or os.environ.get("SF_USER") or data.get("username")
        project = os.environ.get("SF_PROJECT") or data.get("project")
        key_path = os.environ.get("SF_KEY_PATH") or os.environ.get("SF_KEY") or data.get("key_path")
        password = os.environ.get("SF_PASSWORD") or data.get("password")
        default_mirror = os.environ.get("SF_DEFAULT_MIRROR") or os.environ.get("SF_MIRROR") or data.get("default_mirror")
        concurrency = int(os.environ.get("SF_CONCURRENCY", data.get("concurrency", 4)))
        chunk_size = int(os.environ.get("SF_CHUNK_SIZE", data.get("chunk_size", 8 * 1024 * 1024)))

        # Default SSH key auto-discovery if key_path not provided
        if not key_path and not password:
            for candidate in ("id_ed25519", "id_rsa", "id_ecdsa"):
                ssh_key = Path.home() / ".ssh" / candidate
                if ssh_key.is_file():
                    key_path = str(ssh_key)
                    break

        return cls(
            username=username,
            project=project,
            key_path=key_path,
            password=password,
            default_mirror=default_mirror,
            concurrency=concurrency,
            chunk_size=chunk_size,
        )

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = []
        if self.username:
            lines.append(f'username = "{self.username}"')
        if self.project:
            lines.append(f'project = "{self.project}"')
        if self.key_path:
            lines.append(f'key_path = "{self.key_path}"')
        if self.default_mirror:
            lines.append(f'default_mirror = "{self.default_mirror}"')
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
