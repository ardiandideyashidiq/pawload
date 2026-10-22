from __future__ import annotations

from vikingfile.api import (
    VikingItem,
    check_file,
    delete_file,
    extract_file_hash,
    get_upload_server,
    list_files,
    rename_file,
)
from vikingfile.client import VikingFileClient
from vikingfile.config import Config
from vikingfile.uploader import UploadResult, upload_file

__all__ = [
    "Config",
    "UploadResult",
    "VikingFileClient",
    "VikingItem",
    "check_file",
    "delete_file",
    "extract_file_hash",
    "get_upload_server",
    "list_files",
    "rename_file",
    "upload_file",
]


def main() -> None:
    import sys

    from rich.console import Console

    from vikingfile.cli import cli

    try:
        cli()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
