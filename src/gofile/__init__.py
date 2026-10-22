from __future__ import annotations

from gofile.api import (
    GoFileItem,
    create_guest_account,
    generate_website_token,
    get_content,
    get_content_id,
)
from gofile.client import GoFileClient
from gofile.config import Config
from gofile.uploader import UploadResult, upload_file

__all__ = [
    "Config",
    "GoFileClient",
    "GoFileItem",
    "UploadResult",
    "create_guest_account",
    "generate_website_token",
    "get_content",
    "get_content_id",
    "upload_file",
]


def main() -> None:
    import sys

    from rich.console import Console

    from gofile.cli import cli

    try:
        cli()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
