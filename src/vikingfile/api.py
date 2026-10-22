from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from curl_cffi import requests

API_BASE = "https://vikingfile.com/api"
DEFAULT_UPLOAD_SERVER = "https://va.vikingfile.com/index2.php"


@dataclass
class VikingItem:
    hash: str
    name: str
    size: int
    exist: bool = True
    downloads: int = 0
    created: datetime | None = None
    url: str | None = None


def extract_file_hash(url_or_hash: str) -> str:
    """Extract VikingFile hash from URL or return raw hash identifier."""
    clean = url_or_hash.strip()
    if clean.startswith(("http://", "https://")):
        parts = clean.rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] == "f":
            return parts[-1]
        return parts[-1]
    return clean


def get_upload_server() -> str:
    """Query Vikingfile API for the active upload server endpoint."""
    url = f"{API_BASE}/get-server"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "server" in data:
                return data["server"]
    except Exception:
        pass
    return DEFAULT_UPLOAD_SERVER


def check_file(file_hash: str) -> VikingItem | None:
    """Check if a file exists on VikingFile and retrieve its metadata."""
    clean_hash = extract_file_hash(file_hash)
    url = f"{API_BASE}/check-file"
    try:
        resp = requests.post(url, data={"hash": clean_hash}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                item_data = data[0]
            elif isinstance(data, dict):
                item_data = data
            else:
                return None

            if item_data.get("exist", False):
                return VikingItem(
                    hash=item_data.get("hash", clean_hash),
                    name=item_data.get("name", "unknown"),
                    size=int(item_data.get("size", 0)),
                    exist=True,
                    url=f"https://vikingfile.com/f/{clean_hash}",
                )
    except Exception:
        pass
    return None


def list_files(
    user: str,
    page: int = 1,
    remote_path: str = "",
) -> list[VikingItem]:
    """List files in user account via VikingFile API."""
    if not user:
        raise ValueError(
            "User hash is required to list VikingFile files. Set via VIKINGFILE_USER or config."
        )

    url = f"{API_BASE}/list-files"
    payload = {"user": user, "page": page}
    if remote_path:
        payload["path"] = remote_path

    resp = requests.post(url, data=payload, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to list VikingFile files: HTTP {resp.status_code}")

    data = resp.json()
    files_data = data.get("files", [])
    items: list[VikingItem] = []
    for f in files_data:
        h = f.get("hash", "")
        items.append(
            VikingItem(
                hash=h,
                name=f.get("name", ""),
                size=int(f.get("size", 0)),
                downloads=int(f.get("downloads", 0)),
                url=f"https://vikingfile.com/f/{h}",
            )
        )
    return items


def delete_file(file_hash: str, user: str) -> bool:
    """Delete a file from VikingFile using user hash."""
    clean_hash = extract_file_hash(file_hash)
    url = f"{API_BASE}/delete-file"
    resp = requests.post(url, data={"hash": clean_hash, "user": user}, timeout=15)
    if resp.status_code == 200:
        res = resp.json()
        return res.get("error") == "success"
    return False


def rename_file(file_hash: str, user: str, new_filename: str) -> bool:
    """Rename a file on VikingFile."""
    clean_hash = extract_file_hash(file_hash)
    url = f"{API_BASE}/rename-file"
    resp = requests.post(
        url,
        data={"hash": clean_hash, "user": user, "filename": new_filename},
        timeout=15,
    )
    if resp.status_code == 200:
        res = resp.json()
        return res.get("error") == "success"
    return False
