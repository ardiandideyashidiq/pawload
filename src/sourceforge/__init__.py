from __future__ import annotations

from sourceforge.client import SourceForgeClient
from sourceforge.config import Config
from sourceforge.mirrors import (
    Mirror,
    TargetInfo,
    fetch_live_mirrors,
    get_best_release,
    parse_target,
)
from sourceforge.sftp import RemoteItem

__all__ = [
    "Config",
    "Mirror",
    "RemoteItem",
    "SourceForgeClient",
    "TargetInfo",
    "fetch_live_mirrors",
    "get_best_release",
    "parse_target",
]


def main() -> None:
    from sourceforge.cli import cli

    cli()
