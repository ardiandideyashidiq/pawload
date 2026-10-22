from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime

from curl_cffi import requests

API_BASE = "https://pixeldrain.com/api"


@dataclass
class PixelDrainItem:
    id: str
    name: str
    size: int
    mime_type: str = ""
    sha256_hash: str | None = None
    views: int = 0
    downloads: int = 0
    date_upload: datetime | None = None
    can_download: bool = True
    url: str | None = None


def extract_file_id(url_or_id: str) -> str:
    """Extract Pixeldrain file ID from URL or return raw identifier."""
    clean = url_or_id.strip()
    if clean.startswith(("http://", "https://")):
        parts = clean.split("?")[0].rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] in ("u", "file"):
            return parts[-1]
        return parts[-1]
    return clean


def get_auth_headers(api_key: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        encoded = base64.b64encode(f":{api_key}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    return headers


def get_file_info(file_id: str, api_key: str | None = None) -> PixelDrainItem | None:
    """Retrieve metadata for a Pixeldrain file."""
    clean_id = extract_file_id(file_id)
    url = f"{API_BASE}/file/{clean_id}/info"
    try:
        resp = requests.get(url, headers=get_auth_headers(api_key), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success", True):
                mtime = None
                date_str = data.get("date_upload")
                if date_str:
                    try:
                        mtime = datetime.fromisoformat(date_str).astimezone(UTC)
                    except Exception:
                        pass
                return PixelDrainItem(
                    id=data.get("id", clean_id),
                    name=data.get("name", clean_id),
                    size=int(data.get("size", 0)),
                    mime_type=data.get("mime_type", ""),
                    sha256_hash=data.get("hash_sha256"),
                    views=int(data.get("views", 0)),
                    downloads=int(data.get("downloads", 0)),
                    date_upload=mtime,
                    can_download=bool(data.get("can_download", True)),
                    url=f"https://pixeldrain.com/u/{clean_id}",
                )
    except Exception:
        pass
    return None


def delete_file(file_id: str, api_key: str) -> bool:
    """Delete a file from Pixeldrain using an API key."""
    if not api_key:
        raise ValueError("API key is required to delete files from Pixeldrain.")

    clean_id = extract_file_id(file_id)
    url = f"{API_BASE}/file/{clean_id}"
    resp = requests.delete(url, headers=get_auth_headers(api_key), timeout=10)
    if resp.status_code in (200, 204):
        data = resp.json() if resp.content else {}
        return data.get("success", True)
    return False


def get_list(list_id: str, api_key: str | None = None) -> list[PixelDrainItem]:
    """Retrieve files from a Pixeldrain list/album."""
    clean_id = extract_file_id(list_id)
    url = f"{API_BASE}/list/{clean_id}"
    resp = requests.get(url, headers=get_auth_headers(api_key), timeout=15)
    if resp.status_code != 200:
        return []

    data = resp.json()
    files_data = data.get("files", [])
    items: list[PixelDrainItem] = []
    for f in files_data:
        fid = f.get("id", "")
        items.append(
            PixelDrainItem(
                id=fid,
                name=f.get("name", fid),
                size=int(f.get("size", 0)),
                mime_type=f.get("mime_type", ""),
                sha256_hash=f.get("hash_sha256"),
                can_download=bool(f.get("can_download", True)),
                url=f"https://pixeldrain.com/u/{fid}",
            )
        )
    return items
