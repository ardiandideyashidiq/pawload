from __future__ import annotations

from pixeldrain.api import (
    PixelDrainItem,
    delete_file,
    extract_file_id,
    get_file_info,
    get_list,
)
from pixeldrain.client import PixelDrainClient
from pixeldrain.config import Config
from pixeldrain.uploader import UploadResult, upload_file

__all__ = [
    "Config",
    "PixelDrainClient",
    "PixelDrainItem",
    "UploadResult",
    "delete_file",
    "extract_file_id",
    "get_file_info",
    "get_list",
    "upload_file",
]


def main() -> None:
    import sys

    from rich.console import Console

    from pixeldrain.cli import cli

    try:
        cli()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
