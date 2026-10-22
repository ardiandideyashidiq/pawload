from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple
from urllib.parse import unquote, urlparse

from curl_cffi import requests
from rich.console import Console
from rich.prompt import Prompt


class Mirror(NamedTuple):
    id: str
    name: str
    location: str





@dataclass
class ResolvedTarget:
    direct_url: str
    content_length: int
    accept_ranges: bool
    filename: str
    mirror_used: str


def fetch_live_mirrors(project: str, remote_path: str) -> list[Mirror]:
    """Fetch live available mirrors for a specific file from SourceForge."""
    clean_path = remote_path.strip().lstrip("/")
    url = f"https://sourceforge.net/settings/mirror_choices?projectname={project}&filename={clean_path}"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return []

        ul_match = re.search(r'<ul id="mirrorList">(.*?)</ul>', resp.text, re.DOTALL)
        if not ul_match:
            return []

        pattern = re.compile(
            r'<li id="([^"]+)">\s*<input[^>]*value="([^,"]+),([^"]*)"[^>]*>.*?<label[^>]*>([^<]+)</label>(?:\s*\(([^)]+)\))?',
            re.DOTALL,
        )
        mirrors: list[Mirror] = []
        for m in pattern.finditer(ul_match.group(1)):
            m_id = m.group(2)
            name = m.group(4).strip()
            loc = (
                m.group(5).strip()
                if m.group(5)
                else ("Closest mirror by GeoIP" if m_id == "autoselect" else "SourceForge Node")
            )
            mirrors.append(Mirror(id=m_id, name=name, location=loc))
        return mirrors
    except Exception:
        return []

def is_file_path(path: str) -> bool:
    if path.endswith("/download"):
        return True
    clean = path.strip("/")
    last = clean.split("/")[-1]
    return "." in last


@dataclass
class TargetInfo:
    project: str
    remote_path: str | None = None
    expected_md5: str | None = None
    is_project_or_dir: bool = False
    remote_dir: str = ""


def get_best_release(project: str) -> dict[str, str] | None:
    """Fetch best/latest release metadata for a project from SourceForge."""
    url = f"https://sourceforge.net/projects/{project}/best_release.json"
    try:
        resp = requests.get(url, timeout=10)
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
    - A project name (to list or download files)
    - A remote path within a project (when project is provided via param or config)
    """
    val = target.strip()

    if val.startswith(("http://", "https://")):
        parsed = urlparse(val)
        path = parsed.path.strip("/")

        # 1. /projects/<project>/files[/<subpath>]
        m_files = re.match(r"^projects/([^/]+)/files(?:/(.*))?$", path)
        if m_files:
            proj = m_files.group(1)
            sub = unquote(m_files.group(2) or "").strip("/")
            if not sub:
                return TargetInfo(project=proj, is_project_or_dir=True, remote_dir="")
            if is_file_path(sub):
                r_path = re.sub(r"/download$", "", sub)
                return TargetInfo(project=proj, remote_path=r_path, is_project_or_dir=False)
            return TargetInfo(project=proj, is_project_or_dir=True, remote_dir=sub)

        # 2. /project/<project>[/<subpath>] (downloads.sourceforge.net)
        m_dl = re.match(r"^project/([^/]+)(?:/(.*))?$", path)
        if m_dl:
            proj = m_dl.group(1)
            sub = unquote(m_dl.group(2) or "").strip("/")
            if sub and is_file_path(sub):
                return TargetInfo(project=proj, remote_path=sub, is_project_or_dir=False)
            return TargetInfo(project=proj, is_project_or_dir=True, remote_dir=sub)

        # 3. /projects/<project>[/] or /p/<project>[/]
        m_proj = re.match(r"^(?:projects|p)/([^/]+)/?$", path)
        if m_proj:
            proj = m_proj.group(1)
            return TargetInfo(project=proj, is_project_or_dir=True, remote_dir="")

        raise ValueError(f"Unrecognized SourceForge URL: {val}")

    if project:
        if not val or val == project:
            return TargetInfo(project=project, is_project_or_dir=True, remote_dir="")
        if is_file_path(val):
            return TargetInfo(project=project, remote_path=val, is_project_or_dir=False)
        return TargetInfo(project=project, is_project_or_dir=True, remote_dir=val)

    if "/" not in val and not is_file_path(val):
        return TargetInfo(project=val, is_project_or_dir=True, remote_dir="")

    raise ValueError(
        f"Cannot determine SourceForge project for '{val}'. Specify -p/--project or pass a SourceForge URL."
    )


def prompt_select_file(
    items: list,
    latest_path: str | None = None,
    console: Console | None = None,
):
    from rich.table import Table

    from sourceforge.config import format_size

    con = console or Console()
    con.print("[bold cyan]Available Files for Download:[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="bold yellow")
    table.add_column("File Name", style="bold")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Modified (UTC)", style="dim")
    table.add_column("Note", style="cyan")

    default_idx = 1
    clean_latest = latest_path.strip().lstrip("/") if latest_path else None

    for idx, item in enumerate(items, start=1):
        clean_item_path = item.path.strip().lstrip("/")
        is_latest = bool(
            clean_latest
            and (clean_item_path == clean_latest or item.name == clean_latest.split("/")[-1])
        )
        if is_latest:
            default_idx = idx
        note = "[bold green]★ Latest Release[/bold green]" if is_latest else ""
        size_str = format_size(item.size)
        mtime_str = item.modified_time.strftime("%Y-%m-%d %H:%M:%S") if item.modified_time else "-"
        table.add_row(str(idx), item.name, size_str, mtime_str, note)

    con.print(table)

    choice = Prompt.ask(
        f"Choose a file to download [1-{len(items)}]",
        choices=[str(i) for i in range(1, len(items) + 1)],
        default=str(default_idx),
        show_choices=False,
    )
    return items[int(choice) - 1]


def prompt_mirror(
    project: str | None = None,
    remote_path: str | None = None,
    console: Console | None = None,
) -> str:
    """Interactively ask user for mirror choice, fetching live mirrors when available."""
    con = console or Console()

    ref_path = remote_path
    if project and not ref_path:
        best = get_best_release(project)
        if best:
            ref_path = best["filename"]

    if project and ref_path:
        live_mirrors = fetch_live_mirrors(project, ref_path)
        if len(live_mirrors) == 1:
            return live_mirrors[0].id
        if len(live_mirrors) > 1:
            from rich.table import Table

            con.print(f"\n[bold cyan]SourceForge Live Mirrors for {ref_path.split('/')[-1]}:[/bold cyan]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", justify="right", style="bold yellow")
            table.add_column("Mirror ID", style="cyan")
            table.add_column("Host / Provider", style="bold")
            table.add_column("Location", style="green")

            for idx, m in enumerate(live_mirrors, start=1):
                note = " (Auto)" if m.id == "autoselect" else ""
                table.add_row(str(idx), f"{m.id}{note}", m.name, m.location)

            con.print(table)
            choice = Prompt.ask(
                f"Choose a mirror [1-{len(live_mirrors)}]",
                choices=[str(i) for i in range(1, len(live_mirrors) + 1)],
                default="1",
                show_choices=False,
            )
            return live_mirrors[int(choice) - 1].id

    return Prompt.ask("Enter mirror ID", default="autoselect")


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
        if interactive_prompt:
            chosen_mirror = prompt_mirror(project=project, remote_path=clean_path, console=console)
        else:
            chosen_mirror = "autoselect"

    initial_url = (
        f"https://downloads.sourceforge.net/project/{project}/{clean_path}?use_mirror={chosen_mirror}"
    )

    resp = requests.get(
        initial_url,
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
