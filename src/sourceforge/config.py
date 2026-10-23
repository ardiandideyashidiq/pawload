from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def get_unified_config_file() -> Path:
    """Resolve active unified config file path."""
    env_path = (
        os.environ.get("PAWLOAD_CONFIG")
        or os.environ.get("SCRAPER_CONFIG")
        or os.environ.get("MULTICLOUD_CONFIG")
        or os.environ.get("CONFIG_FILE")
    )
    if env_path:
        return Path(env_path).expanduser()

    pawload_cfg = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "pawload"
        / "config.toml"
    )
    if pawload_cfg.is_file():
        return pawload_cfg

    scraper_cfg = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "scraper"
        / "config.toml"
    )
    if scraper_cfg.is_file():
        return scraper_cfg

    sf_cfg = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "sourceforge"
        / "config.toml"
    )
    if sf_cfg.is_file():
        return sf_cfg

    return pawload_cfg


CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pawload"
)
CONFIG_FILE = get_unified_config_file()


def _format_toml_kv(k: str, v: Any) -> str:
    if isinstance(v, bool):
        return f"{k} = {'true' if v else 'false'}"
    if isinstance(v, (int, float)):
        return f"{k} = {v}"
    if isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'{k} = "{escaped}"'
    return f'{k} = "{v}"'


def dump_toml(data: dict[str, Any]) -> str:
    """Serialize dictionary with optional tables to clean TOML text."""
    lines = ["# Multi-Cloud Unified Configuration", ""]
    top_keys = False
    for k, v in data.items():
        if not isinstance(v, dict) and v is not None:
            lines.append(_format_toml_kv(k, v))
            top_keys = True
    if top_keys:
        lines.append("")

    preferred_order = [
        "global",
        "sourceforge",
        "gofile",
        "vikingfile",
        "pixeldrain",
        "telegram",
    ]
    remaining = [k for k in data if k not in preferred_order]
    ordered_keys = [k for k in preferred_order if k in data] + remaining

    for section in ordered_keys:
        subdict = data[section]
        if isinstance(subdict, dict) and subdict:
            lines.append(f"[{section}]")
            for k, v in subdict.items():
                if v is not None:
                    lines.append(_format_toml_kv(k, v))
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def load_section(
    section: str,
    config_file: Path | None = None,
    legacy_file: Path | None = None,
) -> dict[str, Any]:
    """Read a specific section from the unified config file with inheritance from [global]."""
    target_file = config_file or get_unified_config_file()

    if target_file.is_file():
        try:
            with open(target_file, "rb") as f:
                root = tomllib.load(f)
            if isinstance(root, dict):
                if section in root and isinstance(root[section], dict):
                    merged = (
                        dict(root.get("global", {}))
                        if isinstance(root.get("global"), dict)
                        else {}
                    )
                    merged.update(root[section])
                    return merged
                if section == "sourceforge" and not any(
                    isinstance(v, dict) for v in root.values()
                ):
                    return root
        except (OSError, tomllib.TOMLDecodeError):
            pass

    if legacy_file and legacy_file.is_file() and legacy_file != target_file:
        try:
            with open(legacy_file, "rb") as f:
                root = tomllib.load(f)
            if isinstance(root, dict):
                return root.get(section, root)
        except (OSError, tomllib.TOMLDecodeError):
            pass

    return {}


def save_section(
    section: str,
    section_data: dict[str, Any],
    config_file: Path | None = None,
) -> None:
    """Save/update a section in the unified config file without overwriting other sections."""
    target_file = config_file or get_unified_config_file()
    target_file.parent.mkdir(parents=True, exist_ok=True)

    root: dict[str, Any] = {}
    if target_file.is_file():
        try:
            with open(target_file, "rb") as f:
                loaded = tomllib.load(f)
                if isinstance(loaded, dict):
                    root = loaded
        except (OSError, tomllib.TOMLDecodeError):
            pass

    if root and not any(isinstance(v, dict) for v in root.values()):
        root = {"sourceforge": root}

    root[section] = {k: v for k, v in section_data.items() if v is not None}

    serialized = dump_toml(root)
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(serialized)


def load_all_sections(config_file: Path | None = None) -> dict[str, Any]:
    """Load all configured sections from unified config file."""
    target_file = config_file or get_unified_config_file()
    if target_file.is_file():
        try:
            with open(target_file, "rb") as f:
                root = tomllib.load(f)
            if isinstance(root, dict):
                return root
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return {}


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
        data = load_section("sourceforge", config_file=CONFIG_FILE)

        username = (
            os.environ.get("SF_USERNAME")
            or os.environ.get("SF_USER")
            or data.get("username")
        )
        project = os.environ.get("SF_PROJECT") or data.get("project")
        key_path = (
            os.environ.get("SF_KEY_PATH")
            or os.environ.get("SF_KEY")
            or data.get("key_path")
        )
        password = os.environ.get("SF_PASSWORD") or data.get("password")
        default_mirror = (
            os.environ.get("SF_DEFAULT_MIRROR")
            or os.environ.get("SF_MIRROR")
            or data.get("default_mirror")
        )
        concurrency = int(os.environ.get("SF_CONCURRENCY", data.get("concurrency", 4)))
        chunk_size = int(
            os.environ.get("SF_CHUNK_SIZE", data.get("chunk_size", 8 * 1024 * 1024))
        )

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
        save_section(
            "sourceforge",
            {
                "username": self.username,
                "project": self.project,
                "key_path": self.key_path,
                "password": self.password,
                "default_mirror": self.default_mirror,
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
