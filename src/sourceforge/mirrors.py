from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import NamedTuple
from urllib.parse import unquote, urlparse

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


@dataclass
class TargetInfo:
    project: str
    remote_path: str
    expected_md5: str | None = None


def get_best_release(project: str) -> dict[str, str] | None:
    """Fetch best/latest release metadata for a project from SourceForge."""
    url = f"https://sourceforge.net/projects/{project}/best_release.json"
    try:
        resp = requests.get(url, headers={"User-Agent": CLI_USER_AGENT}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            rel = data.get("release")
            if rel and "filename" in rel:
                return {
                    "filename": rel["filename"].lstrip("/"),
                    "md5": rel.get("md5sum"),
                    "bytes": rel.get("bytes"),
                }
    except Exception:
        pass
    return None


def parse_target(target: str, project: str | None = None) -> TargetInfo:
    """
    Parses a target string which can be:
    - A SourceForge URL (project URL, files URL, or direct download URL)
    - A project name (to download the latest release)
    - A remote path within a project (when project is provided via param or config)
    """
    val = target.strip()

    if val.startswith(("http://", "https://")):
        parsed = urlparse(val)
        path = parsed.path.strip("/")

        # 1. /projects/<project>/files/<subpath>[/download]
        m_files = re.match(r"^projects/([^/]+)/files/(.+?)(?:/download)?/?$", path)
        if m_files:
            proj = m_files.group(1)
            r_path = unquote(m_files.group(2))
            return TargetInfo(project=proj, remote_path=r_path)

        # 2. /project/<project>/<subpath> (downloads.sourceforge.net)
        m_dl = re.match(r"^project/([^/]+)/(.+?)/?$", path)
        if m_dl:
            proj = m_dl.group(1)
            r_path = unquote(m_dl.group(2))
            return TargetInfo(project=proj, remote_path=r_path)

        # 3. /projects/<project>[/] or /p/<project>[/]
        m_proj = re.match(r"^(?:projects|p)/([^/]+)/?$", path)
        if m_proj:
            proj = m_proj.group(1)
            best = get_best_release(proj)
            if not best:
                raise ValueError(f"No release found for project '{proj}'")
            return TargetInfo(
                project=proj,
                remote_path=best["filename"],
                expected_md5=best.get("md5"),
            )

        raise ValueError(f"Unrecognized SourceForge URL: {val}")

    if project:
        if not val or val == project:
            best = get_best_release(project)
            if not best:
                raise ValueError(f"No release found for project '{project}'")
            return TargetInfo(
                project=project,
                remote_path=best["filename"],
                expected_md5=best.get("md5"),
            )
        return TargetInfo(project=project, remote_path=val)

    if "/" not in val:
        best = get_best_release(val)
        if best:
            return TargetInfo(
                project=val,
                remote_path=best["filename"],
                expected_md5=best.get("md5"),
            )

    raise ValueError(
        f"Cannot determine SourceForge project for '{val}'. Specify -p/--project or pass a SourceForge URL."
    )


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
