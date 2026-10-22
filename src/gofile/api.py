from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode

from curl_cffi import requests

USER_AGENT = "Mozilla/5.0"
LOCALE = "en-US"
TOKEN_WINDOW_SEC = 14400
DEFAULT_TOKEN_SECRET = "12af056dacea0b"

API_BASE = "https://api.gofile.io"
UPLOAD_URL = "https://upload.gofile.io/uploadfile"


@dataclass
class GoFileItem:
    id: str
    name: str
    is_dir: bool
    size: int
    link: str | None = None
    md5: str | None = None
    mimetype: str | None = None
    modified_time: datetime | None = None
    children_count: int = 0


def get_content_id(url_or_id: str) -> str:
    """Extract content ID from GoFile URL or return raw identifier."""
    clean = url_or_id.strip()
    if clean.startswith(("http://", "https://")):
        parts = clean.rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] == "d":
            return parts[-1]
        return parts[-1]
    return clean


def generate_website_token(account_token: str, secret: str = DEFAULT_TOKEN_SECRET) -> str:
    """Generate dynamic X-Website-Token for GoFile API."""
    time_window = str(int(time.time()) // TOKEN_WINDOW_SEC)
    token_seed = f"{USER_AGENT}::{LOCALE}::{account_token}::{time_window}::{secret}"
    return hashlib.sha256(token_seed.encode()).hexdigest()


def get_auth_headers(account_token: str) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Authorization": f"Bearer {account_token}",
        "X-Website-Token": generate_website_token(account_token),
        "X-BL": LOCALE,
        "Accept": "*/*",
    }


def create_guest_account() -> dict[str, str]:
    """Create a new anonymous guest account on GoFile."""
    resp = requests.post(
        f"{API_BASE}/accounts",
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to create guest account: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("status") != "ok":
        api_status = data.get("status", "unknown error")
        raise RuntimeError(f"GoFile account creation error: {api_status}")
    return {
        "token": data["data"]["token"],
        "account_id": data["data"]["id"],
        "root_folder": data["data"]["rootFolder"],
    }


def get_content(
    content_id: str,
    token: str,
    password: str | None = None,
) -> dict:
    """Fetch folder or file metadata from GoFile API."""
    query: dict[str, str] = {
        "cache": "true",
        "sortField": "createTime",
        "sortDirection": "1",
    }
    if password:
        query["password"] = hashlib.sha256(password.encode()).hexdigest()

    url = f"{API_BASE}/contents/{content_id}?{urlencode(query)}"
    resp = requests.get(url, headers=get_auth_headers(token), timeout=20)
    data = resp.json()

    status = data.get("status")
    if status != "ok":
        if status == "error-notPremium":
            raise PermissionError(
                f"GoFile content '{content_id}' requires a Premium account or is restricted."
            )
        if status == "error-password":
            raise PermissionError(f"GoFile content '{content_id}' requires a password.")
        if status == "error-rateLimit":
            raise RuntimeError("GoFile rate limit exceeded. Please wait a moment or configure a personal token.")
        raise RuntimeError(f"GoFile API returned status: {status}")

    return data["data"]


def parse_content_items(data: dict) -> list[GoFileItem]:
    """Parse API content dict into list of GoFileItem objects."""
    items: list[GoFileItem] = []

    content_type = data.get("type", "file")
    if content_type == "folder" and "children" in data:
        children = data["children"]
        for child_id, child in children.items():
            is_dir = child.get("type") == "folder"
            mtime = None
            create_time = child.get("createTime")
            if create_time:
                mtime = datetime.fromtimestamp(create_time, tz=UTC)
            items.append(
                GoFileItem(
                    id=child.get("id", child_id),
                    name=child.get("name", child_id),
                    is_dir=is_dir,
                    size=child.get("size", 0),
                    link=child.get("link"),
                    md5=child.get("md5"),
                    mimetype=child.get("mimetype"),
                    modified_time=mtime,
                    children_count=child.get("childrenCount", 0),
                )
            )
    else:
        mtime = None
        create_time = data.get("createTime")
        if create_time:
            mtime = datetime.fromtimestamp(create_time, tz=UTC)
        items.append(
            GoFileItem(
                id=data.get("id", ""),
                name=data.get("name", "file"),
                is_dir=False,
                size=data.get("size", 0),
                link=data.get("link"),
                md5=data.get("md5"),
                mimetype=data.get("mimetype"),
                modified_time=mtime,
            )
        )

    return sorted(items, key=lambda x: (not x.is_dir, x.name.lower()))
