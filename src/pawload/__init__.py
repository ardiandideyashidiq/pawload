from __future__ import annotations

import sys

# Provider Clients & Core APIs
from gofile.client import GoFileClient
from gofile.uploader import UploadResult as GoFileUploadResult
from pawload.api import (
    detect_provider,
    download,
    download_async,
    upload,
    upload_async,
)
from pawload.cli import cli
from pixeldrain.client import PixelDrainClient
from pixeldrain.uploader import UploadResult as PixelDrainUploadResult
from rich.console import Console
from sourceforge.client import SourceForgeClient
from sourceforge.downloader import download_file_async as download_sourceforge_file_async
from sourceforge.mirrors import (
    Mirror,
    TargetInfo,
    fetch_live_mirrors,
    get_best_release,
    parse_target,
    resolve_download_target,
)
from sourceforge.sftp import RemoteItem, open_sftp, upload_file_sftp
from telegram.client import TelegramClient
from telegram.reporter import TelegramProgressReporter, create_reporter
from vikingfile.client import VikingFileClient
from vikingfile.uploader import UploadResult as VikingFileUploadResult

__all__ = [
    "GoFileClient",
    "GoFileUploadResult",
    "Mirror",
    "PixelDrainClient",
    "PixelDrainUploadResult",
    "RemoteItem",
    "SourceForgeClient",
    "TargetInfo",
    "TelegramClient",
    "TelegramProgressReporter",
    "VikingFileClient",
    "VikingFileUploadResult",
    "cli",
    "create_reporter",
    "detect_provider",
    "download",
    "download_async",
    "download_sourceforge_file_async",
    "fetch_live_mirrors",
    "get_best_release",
    "main",
    "open_sftp",
    "parse_target",
    "resolve_download_target",
    "upload",
    "upload_async",
    "upload_file_sftp",
]


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
