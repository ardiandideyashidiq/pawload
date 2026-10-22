from __future__ import annotations

from sourceforge.client import SourceForgeClient
from sourceforge.config import Config
from sourceforge.mirrors import REGIONS, Mirror, Region
from sourceforge.sftp import RemoteItem

__all__ = [
    "REGIONS",
    "Config",
    "Mirror",
    "Region",
    "RemoteItem",
    "SourceForgeClient",
]


def main() -> None:
    from sourceforge.cli import cli

    cli()
