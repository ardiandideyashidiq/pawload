# Pawload Python SDK API Reference

`pawload` is a multi-cloud file transfer, scraping, and storage library for Python 3.13+. It provides high-level unified functions for uploads/downloads across multiple providers as well as fine-grained provider clients and async primitives.

---

## Table of Contents
- [Installation](#installation)
- [Quickstart](#quickstart)
- [High-Level Unified API](#high-level-unified-api)
  - [`pawload.upload`](#pawloadupload)
  - [`pawload.upload_async`](#pawloadupload_async)
  - [`pawload.download`](#pawloaddownload)
  - [`pawload.download_async`](#pawloaddownload_async)
  - [`pawload.detect_provider`](#pawloaddetect_provider)
- [SourceForge Capabilities](#sourceforge-capabilities)
  - [`SourceForgeClient`](#sourceforgeclient)
  - [Mirror Management & Live Probing](#mirror-management--live-probing)
  - [Low-Level SFTP & Downloader Primitives](#low-level-sftp--downloader-primitives)
- [GoFile Capabilities](#gofile-capabilities)
  - [`GoFileClient`](#gofileclient)
- [PixelDrain Capabilities](#pixeldrain-capabilities)
  - [`PixelDrainClient`](#pixeldrainclient)
- [VikingFile Capabilities](#vikingfile-capabilities)
  - [`VikingFileClient`](#vikingfileclient)
- [Telegram Notifications & Progress](#telegram-notifications--progress)
  - [`TelegramClient`](#telegramclient)
  - [`create_reporter`](#create_reporter)
- [Configuration & Inheritance](#configuration--inheritance)

---

## Installation

```bash
# Using uv:
uv add pawload

# Using pip:
pip install pawload
```

---

## Quickstart

```python
import pawload

# 1. Automatic multi-cloud download (auto-detects provider from URL or shorthand)
local_file = pawload.download("https://gofile.io/d/abc123", output_path="./downloads/")

# 2. Upload file to SourceForge FRS via SFTP
remote_target = pawload.upload(
    "dist/app-v1.0.tar.gz",
    provider="sourceforge",
    project="my-project",
    remote_dir="release",
    force=True,
)

# 3. Upload file to GoFile with real-time streaming
res = pawload.upload("backup.sql.gz", provider="gofile")
print("Share Link:", res.download_page)
```

---

## High-Level Unified API

The top-level package exposes unified synchronous and asynchronous methods.

### `pawload.upload`
```python
def upload(
    file_path: str | Path,
    provider: str = "gofile",
    remote_path: str = "",
    *,
    project: str | None = None,
    username: str | None = None,
    key_path: str | None = None,
    token: str | None = None,
    api_key: str | None = None,
    user: str | None = None,
    force: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Any
```
- **`provider`**: `"sourceforge"` (`"sf"`), `"gofile"` (`"gf"`), `"pixeldrain"` (`"pd"`), or `"vikingfile"` (`"vf"`).
- **`remote_path`**: Destination folder ID (GoFile), subpath (VikingFile), or remote directory (SourceForge).
- **`progress_callback`**: Callback accepting `(completed_bytes: int, total_bytes: int)`.
- **Returns**: Remote file path string (for SourceForge) or `UploadResult` object containing `.url` / `.download_page`.

### `pawload.upload_async`
Asynchronous counterpart to `upload()`.
```python
import asyncio
import pawload

async def main():
    await pawload.upload_async("archive.zip", provider="gofile")

asyncio.run(main())
```

---

### `pawload.download`
```python
def download(
    target: str,
    output_path: str | Path | None = None,
    *,
    provider: str | None = None,
    project: str | None = None,
    mirror: str | None = None,
    concurrency: int | None = None,
    verify_checksum: bool = True,
    token: str | None = None,
    api_key: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path
```
- **`target`**: Full HTTP URL or provider shorthand:
  - SourceForge: `https://sourceforge.net/projects/<proj>/files/...`, `sf:<proj>/<file>`, or `<proj>/<file>`
  - GoFile: `https://gofile.io/d/<id>` or `gf:<id>`
  - Pixeldrain: `https://pixeldrain.com/u/<id>` or `pd:<id>`
  - VikingFile: `https://vikingfile.com/f/<hash>` or `vf:<hash>`
- **`output_path`**: Target file destination or directory (ending in `/`).
- **`concurrency`**: Number of parallel chunk workers (default from config or 4).
- **`verify_checksum`**: Validates MD5 or SHA256 when metadata is available.
- **Returns**: Local `pathlib.Path` of the downloaded file.

### `pawload.download_async`
Asynchronous counterpart to `download()`.

---

### `pawload.detect_provider`
Detects the target cloud host from a URL or string:
```python
from pawload import detect_provider

detect_provider("https://gofile.io/d/abc")        # 'gofile'
detect_provider("sf:myproject/release/app.zip")    # 'sourceforge'
detect_provider("https://pixeldrain.com/u/1234")   # 'pixeldrain'
detect_provider("https://vikingfile.com/f/hash")   # 'vikingfile'
```

---

## SourceForge Capabilities

### `SourceForgeClient`
Unified client for SourceForge operations over SFTP and parallel chunked downloads over HTTP:
```python
from pawload import SourceForgeClient

client = SourceForgeClient(
    project="my-project",
    username="sf-user",                 # Optional if in config.toml
    key_path="~/.ssh/id_ed25519",       # Optional if in config.toml
)

# 1. Download file with automatic mirror selection
dest = client.download(
    "release/app-v1.0.tar.gz",
    output_path="./downloads/",
    mirror="autoselect",
    concurrency=8,
)

# 2. Upload file via SFTP with automated directory creation
remote_target = client.upload(
    local_path="./dist/app-v1.0.tar.gz",
    remote_dir="release",
    force=True,
)

# 3. Remote SFTP file management
files = client.list(remote_dir="release")
for f in files:
    print(f.name, f.size, f.is_dir)

client.rename("release/app-v1.0.tar.gz", "release/app-v1.0-final.tar.gz")
client.delete("release/old-build.tar.gz")
```

### Mirror Management & Live Probing
Probe active mirror hosts before downloading:
```python
from pawload import fetch_live_mirrors, resolve_download_target

mirrors = fetch_live_mirrors("my-project", "release/app-v1.0.tar.gz")
for m in mirrors:
    print(m.id, m.name, m.country)

# Resolve direct CDN target:
resolved = resolve_download_target("my-project", "release/app-v1.0.tar.gz", mirror="autoselect")
print("Direct URL:", resolved.direct_url)
print("Content Length:", resolved.content_length)
```

### Low-Level SFTP & Downloader Primitives
```python
import asyncio
from pawload import open_sftp, upload_file_sftp, download_sourceforge_file_async

async def custom_transfer():
    # Direct SFTP session manager
    async with open_sftp(username="sf-user", key_path="~/.ssh/id_ed25519") as sftp:
        await upload_file_sftp(sftp, "file.bin", project="my-project", remote_dir="custom")

    # Direct parallel chunk downloader
    path = await download_sourceforge_file_async(
        project="my-project",
        remote_path="custom/file.bin",
        output_path="./file.bin",
        concurrency=4,
    )

asyncio.run(custom_transfer())
```

---

## GoFile Capabilities

### `GoFileClient`
```python
from pawload import GoFileClient

client = GoFileClient(token="your-gofile-token")  # Omit token for guest mode

# Chunked parallel streaming upload:
result = client.upload("dataset.tar", folder_id="folder-id")
print("Page URL:", result.download_page)
print("File ID:", result.file_id)

# Download file or folder:
paths = client.download("https://gofile.io/d/abc123", output_path="./out/")
```

---

## PixelDrain Capabilities

### `PixelDrainClient`
```python
from pawload import PixelDrainClient

client = PixelDrainClient(api_key="your-key")  # Omit for anonymous

result = client.upload("archive.zip")
print("Share Link:", result.url)

client.download("https://pixeldrain.com/u/xyz", output_path="./archive.zip")
info = client.info("xyz")
print("Size:", info.size, "SHA256:", info.sha256)
client.delete("xyz")
```

---

## VikingFile Capabilities

### `VikingFileClient`
```python
from pawload import VikingFileClient

client = VikingFileClient(user="user-hash")

result = client.upload("installer.exe", remote_path="builds")
print("Share Link:", result.url)

# File metadata check
item = client.check("hash123")
print("Name:", item.name, "Size:", item.size)

# List account files
items = client.list(remote_path="builds")
client.rename("hash123", "new_installer.exe")
client.delete("hash123")
```

---

## Telegram Notifications & Progress

Stream upload/download progress cards directly to Telegram topics or channels:
```python
from pawload import TelegramClient, create_reporter

# 1. Client usage
tg = TelegramClient(bot_token="123456:ABC...", chat_id="6665891737")
tg.send_message("<b>Deploy started!</b>")

# 2. Automated progress reporter
reporter = create_reporter(title="GoFile: bigfile.iso", target_name="bigfile.iso")
# Passes progress callbacks to any download or upload:
pawload.download(
    "https://gofile.io/d/abc",
    progress_callback=lambda copied, total: reporter.update(copied, total) if reporter else None
)
if reporter:
    reporter.finish(success_url="https://gofile.io/d/abc")
```

---

## Configuration & Inheritance

`pawload` resolves active configuration with the following precedence:
1. `PAWLOAD_CONFIG` environment variable (or `CONFIG_FILE`)
2. `~/.config/pawload/config.toml` (via `$XDG_CONFIG_HOME`)

### Sample `config.toml`:
```toml
[global]
concurrency = 6

[sourceforge]
username = "sf-dev"
project = "my-project"
key_path = "~/.ssh/id_ed25519"
default_mirror = "autoselect"

[gofile]
token = "ZCXFB6pBWMEWaCNEARTKCu8j7clo8GNQ"

[pixeldrain]
api_key = "00ac1cb3-4df2-40f2-9f41-094db1cb18d0"

[vikingfile]
user = "f3gmgZDa8z"

[telegram]
bot_token = "8883276964:AAHJxX84I9aDtt6CIbVEj3TFhCPZgG3DtxY"
chat_id = "6665891737"
thread_id = 1
throttle_interval = 2.0
```
