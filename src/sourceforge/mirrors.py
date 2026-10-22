from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import NamedTuple

from curl_cffi import requests
from rich.console import Console
from rich.prompt import Prompt

CLI_USER_AGENT = "curl/8.0"


class Mirror(NamedTuple):
    id: str
    name: str
    location: str


class Region(NamedTuple):
    name: str
    mirrors: list[Mirror]


REGIONS: dict[str, Region] = {
    "auto": Region(
        name="Auto-Select (Recommended)",
        mirrors=[Mirror("autoselect", "SourceForge Geo-Director", "Closest mirror by GeoIP")],
    ),
    "master": Region(
        name="Master Authoritative (Fast & Global)",
        mirrors=[Mirror("master", "SourceForge Master Node", "Global Authoritative")],
    ),
    "na": Region(
        name="North America",
        mirrors=[
            Mirror("cfhcable", "Cfhcable", "Tampa, FL, United States"),
            Mirror("gigenet", "GigeNET", "Chicago / Fayetteville, United States"),
            Mirror("cytranet", "Cytranet", "Dallas / Las Vegas, United States"),
            Mirror("pilotfiber", "Pilotfiber", "New York, NY, United States"),
        ],
    ),
    "eu": Region(
        name="Europe",
        mirrors=[
            Mirror("delska", "Delska", "Frankfurt, Germany / Amsterdam, Netherlands"),
            Mirror("altushost", "AltusHost", "Netherlands / Sweden / Bulgaria"),
            Mirror("unlimited", "UNLIMITED.RS", "Belgrade, Serbia"),
        ],
    ),
    "asia": Region(
        name="Asia-Pacific",
        mirrors=[
            Mirror("twds", "TWDS", "Taipei, Taiwan"),
            Mirror("excellmedia", "Excell Media", "Hyderabad, India"),
            Mirror("ixpeering", "IX Australia", "Brisbane, Australia"),
        ],
    ),
}


@dataclass
class ResolvedTarget:
    direct_url: str
    content_length: int
    accept_ranges: bool
    filename: str
    mirror_used: str


def prompt_mirror(console: Console | None = None) -> str:
    """Interactively ask user for their preferred region and mirror."""
    con = console or Console()
    con.print("[bold cyan]SourceForge Download Mirror Selection[/bold cyan]")
    
    region_keys = list(REGIONS.keys())
    for idx, key in enumerate(region_keys, start=1):
        reg = REGIONS[key]
        con.print(f"  [bold yellow]{idx}[/bold yellow]. {reg.name}")

    choice = Prompt.ask(
        "Choose a region",
        choices=[str(i) for i in range(1, len(region_keys) + 1)],
        default="1",
        show_choices=False,
    )
    chosen_region = REGIONS[region_keys[int(choice) - 1]]

    if len(chosen_region.mirrors) == 1:
        return chosen_region.mirrors[0].id

    con.print(f"\n[cyan]Mirrors in {chosen_region.name}:[/cyan]")
    for idx, m in enumerate(chosen_region.mirrors, start=1):
        con.print(f"  [bold yellow]{idx}[/bold yellow]. {m.name} ({m.location})")

    mirror_choice = Prompt.ask(
        "Choose a mirror",
        choices=[str(i) for i in range(1, len(chosen_region.mirrors) + 1)],
        default="1",
        show_choices=False,
    )
    return chosen_region.mirrors[int(mirror_choice) - 1].id


def resolve_download_target(
    project: str,
    remote_path: str,
    mirror: str | None = None,
    interactive_prompt: bool = True,
    console: Console | None = None,
) -> ResolvedTarget:
    clean_path = remote_path.strip().lstrip("/")

    chosen_mirror = mirror
    if not chosen_mirror:
        if interactive_prompt and sys.stdin.isatty():
            chosen_mirror = prompt_mirror(console)
        else:
            chosen_mirror = "autoselect"

    initial_url = (
        f"https://downloads.sourceforge.net/project/{project}/{clean_path}?use_mirror={chosen_mirror}"
    )

    resp = requests.get(
        initial_url,
        headers={"User-Agent": CLI_USER_AGENT},
        allow_redirects=True,
        stream=True,
    )
    if resp.status_code not in (200, 206):
        raise RuntimeError(
            f"Failed to resolve download URL for {project}/{clean_path} (HTTP {resp.status_code})"
        )

    direct_url = resp.url
    cl_header = resp.headers.get("content-length")
    content_length = int(cl_header) if cl_header and cl_header.isdigit() else 0
    accept_ranges = "bytes" in resp.headers.get("accept-ranges", "").lower()

    # Determine filename from URL or path
    filename = clean_path.split("/")[-1]
    cd = resp.headers.get("content-disposition", "")
    if "filename=" in cd:
        for part in cd.split(";"):
            if "filename=" in part:
                filename = part.split("=")[-1].strip().strip('"')
                break

    return ResolvedTarget(
        direct_url=direct_url,
        content_length=content_length,
        accept_ranges=accept_ranges,
        filename=filename,
        mirror_used=chosen_mirror,
    )
