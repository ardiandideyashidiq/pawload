from __future__ import annotations

import sys

from rich.console import Console

from gdrive.api import (
    GDriveItem,
    extract_gdrive_id,
    inspect_target,
    inspect_target_async,
    list_folder,
    load_cookies,
    resolve_direct_download,
)
from gdrive.client import GDriveClient
from gdrive.config import Config
from gdrive.downloader import download_file_async

__all__ = [
    "Config",
    "GDriveClient",
    "GDriveItem",
    "download_file_async",
    "extract_gdrive_id",
    "inspect_target",
    "inspect_target_async",
    "list_folder",
    "load_cookies",
    "main",
    "resolve_direct_download",
]


def main() -> None:
    from gdrive.cli import cli

    try:
        cli()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
