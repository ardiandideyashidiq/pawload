from __future__ import annotations

import http.cookiejar
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from curl_cffi.requests import AsyncSession

from gdrive.config import Config, find_default_cookie_file


@dataclass
class GDriveItem:
    id: str
    name: str
    size: int = 0
    mime_type: str = ""
    is_folder: bool = False
    direct_url: str | None = None
    children: list[GDriveItem] = field(default_factory=list)


def extract_gdrive_id(url_or_id: str) -> str:
    """Extract Google Drive file or folder ID from various URL formats or shorthand."""
    clean = url_or_id.strip()
    if clean.startswith(("gd:", "gdrive:")):
        clean = clean.split(":", 1)[1].strip()

    # Query param ?id=... or &id=...
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]{20,50})", clean)
    if m:
        return m.group(1)

    # Path /d/<id> or /folders/<id>
    m = re.search(r"/(?:d|folders)/([a-zA-Z0-9_-]{20,50})", clean)
    if m:
        return m.group(1)

    # Bare ID
    if re.match(r"^[a-zA-Z0-9_-]{20,50}$", clean):
        return clean

    return clean


def parse_cookie_string(raw: str) -> dict[str, str]:
    """Parse raw cookie header string ('k=v; k2=v2') or JSON format."""
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith(("[", "{")):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return {
                    item["name"]: item["value"]
                    for item in data
                    if isinstance(item, dict) and "name" in item and "value" in item
                }
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
    cookies: dict[str, str] = {}
    if ";" in raw or "=" in raw:
        for item in raw.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                cookies[k.strip()] = v.strip()
    return cookies


def load_cookies(
    cookie_input: dict[str, str] | str | Path | None = None,
) -> dict[str, str]:
    """
    Load Google cookies from:
    1. A dictionary of cookies
    2. A raw cookie string ("SID=...; HSID=..." or JSON format)
    3. A Netscape / JSON cookie file path
    4. Environment variables (GDRIVE_COOKIE, GDRIVE_COOKIES, GDRIVE_COOKIE_FILE, PAWLOAD_COOKIE)
    5. Config or default cookie.txt location
    """
    import os

    if isinstance(cookie_input, dict):
        return dict(cookie_input)

    # 1. Check if cookie_input is a direct raw string (contains '=' or JSON and not an existing file)
    if isinstance(cookie_input, str):
        clean_str = cookie_input.strip()
        p = Path(clean_str).expanduser()
        if not p.is_file() and ("=" in clean_str or clean_str.startswith(("[", "{"))):
            parsed = parse_cookie_string(clean_str)
            if parsed:
                return parsed

    # 2. Check if cookie_input is an existing file
    target_path: Path | None = None
    if cookie_input:
        p = Path(cookie_input).expanduser()
        if p.is_file():
            target_path = p

    # 3. Check environment variables
    if not target_path:
        env_cookie = (
            os.environ.get("GDRIVE_COOKIE")
            or os.environ.get("GDRIVE_COOKIES")
            or os.environ.get("PAWLOAD_COOKIE")
        )
        if env_cookie:
            parsed = parse_cookie_string(env_cookie)
            if parsed:
                return parsed
        env_file = os.environ.get("GDRIVE_COOKIE_FILE") or os.environ.get("PAWLOAD_COOKIE_FILE")
        if env_file and Path(env_file).expanduser().is_file():
            target_path = Path(env_file).expanduser()

    # 4. Check config and default candidate locations
    if not target_path:
        cfg = Config.load()
        if cfg.cookie_file and Path(cfg.cookie_file).is_file():
            target_path = Path(cfg.cookie_file)
        else:
            target_path = find_default_cookie_file()

    if not target_path or not target_path.is_file():
        return {}

    try:
        cj = http.cookiejar.MozillaCookieJar(str(target_path))
        cj.load(ignore_discard=True, ignore_expires=True)
        res = {c.name: c.value for c in cj if "google.com" in c.domain or not c.domain}
        if res:
            return res
    except Exception:
        pass

    try:
        content = target_path.read_text(errors="ignore").strip()
        parsed = parse_cookie_string(content)
        if parsed:
            return parsed

        # Fallback tab-separated Netscape parser
        cookies = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]
        return cookies
    except Exception:
        return {}

def extract_filename_from_cd(cd: str) -> str | None:
    """Extract filename from Content-Disposition header."""
    if not cd:
        return None
    m = re.search(r"filename\*=(?:UTF-8'')?([^;]+)", cd, re.IGNORECASE)
    if m:
        return urllib.parse.unquote(m.group(1).strip("\"'"))
    m = re.search(r"filename=([^;]+)", cd, re.IGNORECASE)
    if m:
        return m.group(1).strip("\"'")
    return None


async def resolve_direct_download(
    file_id: str,
    cookies: dict[str, str] | None = None,
    session: AsyncSession | None = None,
) -> tuple[str, str, int]:
    """
    Resolve Google Drive direct download URL, filename, and size.
    Handles virus scan warning multi-step token confirmation without downloading the file.
    Returns: (direct_download_url, filename, total_size_bytes)
    """
    url = f"https://drive.google.com/uc?id={file_id}&export=download"
    owns_session = session is None
    s = session or AsyncSession(cookies=cookies)

    try:
        current_url = url
        final_url = url
        filename: str | None = None
        total_size = 0

        # Follow redirects and form confirmations (up to 5 steps)
        for _ in range(5):
            if "accounts.google.com" in current_url:
                raise PermissionError(
                    f"Google Drive item '{file_id}' requires login authentication. "
                    "Please provide cookies via --cookie / --cookie-file, GDRIVE_COOKIE env, or config."
                )
            resp = await s.get(current_url, stream=True, allow_redirects=False)
            if resp.status_code in (401, 403):
                raise PermissionError(
                    f"Access denied (HTTP {resp.status_code}) for Google Drive item '{file_id}'. "
                    "The file is private and requires a valid login cookie."
                )
            if resp.status_code in (301, 302, 303, 307, 308):
                current_url = resp.headers["location"]
                if "accounts.google.com" in current_url:
                    raise PermissionError(
                        f"Google Drive item '{file_id}' requires login authentication. "
                        "Please provide cookies via --cookie / --cookie-file, GDRIVE_COOKIE env, or config."
                    )
                final_url = current_url
                continue
            ct = resp.headers.get("content-type", "").lower()
            if "text/html" in ct:
                chunks = []
                async for c in resp.aiter_content():
                    chunks.append(c)
                body = b"".join(chunks).decode("utf-8", errors="ignore")

                if "download-form" in body:
                    m_act = re.search(
                        r'<form[^>]+id=[\"\']download-form[\"\'][^>]+action=[\"\']([^\s\"\']+)[\"\']',
                        body,
                    )
                    action = (
                        m_act.group(1)
                        if m_act
                        else "https://drive.usercontent.google.com/download"
                    )
                    inputs = re.findall(
                        r'<input[^>]+name=[\"\']([^\"\']+)[\"\'][^>]+value=[\"\']([^\"\']*)[\"\']',
                        body,
                    )
                    if not inputs:
                        inputs = re.findall(
                            r'<input[^>]+value=[\"\']([^\"\']*)[\"\'][^>]+name=[\"\']([^\"\']+)[\"\']',
                            body,
                        )
                        inputs = [(k, v) for v, k in inputs]
                    params = dict(inputs)
                    query = "&".join(f"{k}={v}" for k, v in params.items())
                    current_url = f"{action}?{query}"
                    final_url = current_url
                    continue
            # Reached direct file stream
            cd = resp.headers.get("content-disposition", "")
            filename = extract_filename_from_cd(cd)
            cl = resp.headers.get("content-length")
            if cl and cl.isdigit():
                total_size = int(cl)
            cr = resp.headers.get("content-range", "")
            if "/" in cr:
                try:
                    total_size = int(cr.split("/")[-1])
                except ValueError:
                    pass
            final_url = current_url
            break

        # Probe with range request for filename and total size if still missing
        if not filename or total_size == 0:
            probe = await s.get(
                final_url,
                headers={"Range": "bytes=0-0"},
                stream=True,
                allow_redirects=False,
            )
            cd = probe.headers.get("content-disposition", "")
            fn = extract_filename_from_cd(cd)
            if fn:
                filename = fn
            cr = probe.headers.get("content-range", "")
            if "/" in cr:
                try:
                    total_size = int(cr.split("/")[-1])
                except ValueError:
                    pass
            elif probe.headers.get("content-length", "").isdigit():
                total_size = int(probe.headers["content-length"])

        return final_url, filename or f"{file_id}.bin", total_size
    finally:
        if owns_session:
            await s.close()


async def inspect_target_async(
    target: str,
    cookies: dict[str, str] | None = None,
) -> GDriveItem:
    """Inspect a Google Drive target URL or ID, determining if it is a folder or file."""
    clean_id = extract_gdrive_id(target)
    c = cookies if cookies is not None else load_cookies()

    async with AsyncSession(cookies=c) as session:
        # Check folder page first
        folder_url = f"https://drive.google.com/drive/folders/{clean_id}"
        resp = await session.get(folder_url, allow_redirects=True)
        if resp.status_code in (401, 403) or "accounts.google.com" in resp.url:
            view_url = f"https://drive.google.com/file/d/{clean_id}/view"
            view_resp = await session.get(view_url, allow_redirects=True)
            if view_resp.status_code in (401, 403) or "accounts.google.com" in view_resp.url:
                raise PermissionError(
                    f"Google Drive item '{clean_id}' is private and requires login authentication. "
                    "Please provide valid cookies via --cookie / --cookie-file, GDRIVE_COOKIE env, or config."
                )
        is_folder = (
            "application/vnd.google-apps.folder" in resp.text
            or "window['_DRIVE_ivd']" in resp.text
            or "window['__DRIVE_ivd']" in resp.text
        )

        if is_folder:
            # Extract folder title
            m_title = re.search(r"<title>(.*?)(?: - Google Drive)?</title>", resp.text)
            folder_title = m_title.group(1).replace(" - Google Drive", "").strip() if m_title else clean_id

            children: list[GDriveItem] = []
            m_ivd = re.search(r"window\[['_]?DRIVE_ivd'\]\s*=\s*'([^']+)'", resp.text)
            if m_ivd:
                try:
                    decoded = m_ivd.group(1).encode().decode("unicode_escape")
                    data = json.loads(decoded)

                    def find_items(obj: object) -> list[GDriveItem]:
                        results: list[GDriveItem] = []
                        if isinstance(obj, list):
                            if (
                                len(obj) >= 4
                                and isinstance(obj[0], str)
                                and isinstance(obj[2], str)
                                and isinstance(obj[3], str)
                                and "/" in obj[3]
                                and obj[3] != "application/vnd.google-apps.folder"
                            ):
                                sz = (
                                    obj[13]
                                    if len(obj) > 13 and isinstance(obj[13], int)
                                    else 0
                                )
                                results.append(
                                    GDriveItem(
                                        id=obj[0],
                                        name=obj[2],
                                        size=sz,
                                        mime_type=obj[3],
                                        is_folder=False,
                                    )
                                )
                            for el in obj:
                                results.extend(find_items(el))
                        return results

                    children = find_items(data)
                except Exception:
                    pass

            # Fallback to HTML data-id attributes if ivd yielded nothing
            if not children:
                matches = re.findall(
                    r'data-id="([a-zA-Z0-9_-]{20,50})"[^>]*data-tooltip="([^"]+)"',
                    resp.text,
                )
                for mid, mname in matches:
                    if mid != clean_id:
                        children.append(GDriveItem(id=mid, name=mname, is_folder=False))

            return GDriveItem(
                id=clean_id,
                name=folder_title,
                is_folder=True,
                children=children,
            )

        # Single file target: resolve direct download URL and metadata
        direct_url, filename, total_size = await resolve_direct_download(
            clean_id, cookies=c, session=session
        )
        return GDriveItem(
            id=clean_id,
            name=filename,
            size=total_size,
            is_folder=False,
            direct_url=direct_url,
        )


def inspect_target(
    target: str,
    cookies: dict[str, str] | None = None,
) -> GDriveItem:
    """Synchronous target inspection."""
    import asyncio

    return asyncio.run(inspect_target_async(target=target, cookies=cookies))


def list_folder(
    folder_id: str,
    cookies: dict[str, str] | None = None,
) -> list[GDriveItem]:
    """List files inside a Google Drive folder."""
    item = inspect_target(folder_id, cookies=cookies)
    return item.children if item.is_folder else [item]
