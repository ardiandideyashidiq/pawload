from __future__ import annotations

import sys

from rich.console import Console

from pawload.cli import cli

__all__ = ["cli", "main"]


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
