# sourceforge

A pure Python client and CLI for SourceForge FRS upload, parallel chunked download, and release management.

## Features

- **Upload (`asyncssh`)**: Native SFTP streaming to `frs.sourceforge.net` with pipelined chunk transfers, auto recursive directory creation (`mkdir -p`), and remote overwrite collision detection.
- **Download (`curl-cffi`)**: Parallel chunked multi-part download (`Range: bytes=start-end`), sparse file in-place writes, dynamic sliding window queue, and resume support via `.sfdownload` state tracking.
- **Mirror Selection**: Interactive regional selection prompt (North America, Europe, Asia-Pacific, Master CDN, Auto-Select) with config persistence.
- **Integrity**: Automatic post-download MD5 checksum validation against SourceForge published RSS metadata.
- **FRS Management**: Real-time SFTP listing/deleting/renaming when authenticated, with public RSS feed fallback for anonymous listing.

---

## CLI Usage

Entrypoint is available as both `sourceforge` and `sf`.

### Configuration
```bash
# View SourceForge configuration or all configured services
sf config show
sf config show --all

# Print path to active unified config file (~/.config/sourceforge/config.toml)
sf config path

# Set default project, username, or mirror
sf config set -p <project> -u <username> -k ~/.ssh/id_ed25519
sf config set --pick-mirror
```

### Unified Configuration File
All CLI tools (`sf`, `gf`, `vf`, `pd`, `tg`) can be configured in a single unified TOML file located at `~/.config/sourceforge/config.toml` (or `~/.config/scraper/config.toml`, or overridden via `SCRAPER_CONFIG` / `MULTICLOUD_CONFIG` / `CONFIG_FILE` environment variable):

```toml
# Shared settings
[global]
concurrency = 4
chunk_size = 8388608

[sourceforge]
project = "my-project"
username = "my-username"
key_path = "~/.ssh/id_ed25519"
default_mirror = "master"

[gofile]
token = "my-gofile-token"

[vikingfile]
user = "my-vikingfile-user-hash"

[pixeldrain]
api_key = "my-pixeldrain-api-key"

[telegram]
bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
chat_id = "-100123456789"
thread_id = 42
throttle_interval = 2.0
parse_mode = "HTML"
```

### Download
```bash
# Download latest release directly from SourceForge project URL
sf download https://sourceforge.net/projects/netmodhttp/

# Download a specific file by URL
sf download https://sourceforge.net/projects/rdndds-release/files/rom/README.md/download

# Download by project name (resolves latest release)
sf download netmodhttp

# Download by remote path with project flag
sf download rom/README.md -p rdndds-release

# Specific mirror, output path, and 8 parallel workers
sf download rom/lineage-23.1-UNOFFICIAL.zip -p rdndds-release -o ~/Downloads/ROM.zip -m master -c 8
```

### Upload
```bash
# Upload via SFTP with automatic directory creation
sf upload ./ROM.zip -p rdndds-release -d rom -u rdndds

# Overwrite existing remote file
sf upload ./ROM.zip -p rdndds-release -d rom -u rdndds --force
```

### File Management
```bash
# List files (public RSS fallback or authenticated SFTP)
sf list rom -p rdndds-release

# Rename or move
sf rename rom/old.zip rom/new.zip -p rdndds-release -u rdndds

# Delete
sf delete rom/old.zip -p rdndds-release -u rdndds
```

---

## Python Library Usage

```python
from sourceforge import SourceForgeClient

# Initialize client
client = SourceForgeClient(project="rdndds-release", username="rdndds")

# Download (with parallel chunks and checksum validation)
client.download(
    "rom/README.md", output_path="README.md", mirror="master", concurrency=4
)

# Upload via SFTP
client.upload("ROM.zip", remote_dir="rom", force=True)

# List remote files
items = client.list("rom")
for item in items:
    print(f"{item.name}: {item.size} bytes (MD5: {item.md5})")

# Native async support
# await client.download_async(...)
# await client.upload_async(...)
```

---

## GoFile CLI & Library

A client and CLI for GoFile.io upload, parallel download, and folder browsing.
Entrypoints: `gofile` and `gf`.

### GoFile CLI Usage
```bash
# Configure personal GoFile account token (optional; auto-creates guest account by default)
gf config set -t <token>

# Download from GoFile folder or file URL (interactive file selection)
gf download https://gofile.io/d/yt9wik0T

# Download all files in folder
gf download https://gofile.io/d/yt9wik0T --all

# Upload a file to GoFile
gf upload ./ROM.zip

# List folder contents
gf list https://gofile.io/d/yt9wik0T
```

### GoFile Python Library Usage
```python
from gofile import GoFileClient

client = GoFileClient()  # auto-manages token

# Download
client.download("https://gofile.io/d/yt9wik0T", output_path="downloaded_file.zip")

# Upload
res = client.upload("./ROM.zip")
print(f"Uploaded to: {res.download_page}")

# List
items = client.list("https://gofile.io/d/yt9wik0T")
for it in items:
    print(f"{it.name} - {it.size} bytes (MD5: {it.md5})")
```

---

## VikingFile CLI & Library

A client and CLI for VikingFile upload, metadata checking, and file management.
Entrypoints: `vikingfile` and `vf`.

### VikingFile CLI Usage
```bash
# Configure default user hash (optional; empty string for anonymous uploads)
vf config set -u <user_hash>

# Upload a file anonymously
vf upload ./ROM.zip

# Upload to account with destination folder
vf upload ./ROM.zip -u <user_hash> -d "ROMs/Android-14"

# Check file details by URL or hash
vf check https://vik1ngfile.site/f/QL0UByzja9
vf check QL0UByzja9

# List files in account
vf list -u <user_hash> -p 1

# Delete or rename file in account
vf rename <hash> "new_name.zip" -u <user_hash>
vf delete <hash> -u <user_hash>
```

### VikingFile Python Library Usage
```python
from vikingfile import VikingFileClient

client = VikingFileClient(user="<user_hash>")

# Upload
res = client.upload("./ROM.zip")
print(f"Uploaded: {res.url} (Hash: {res.hash})")

# Check
info = client.check("QL0UByzja9")
if info and info.exist:
    print(f"{info.name} ({info.size} bytes)")
```

---

## Pixeldrain CLI & Library

A client and CLI for Pixeldrain upload, parallel download, and file inspection.
Entrypoints: `pixeldrain` and `pd`.

### Pixeldrain CLI Usage
```bash
# Configure API key (optional for downloads/info; required for uploads/deletes)
pd config set -k <api_key>

# Download file by URL or ID (parallel chunks + automatic SHA256 verification)
pd download https://pixeldrain.com/u/SCSZUyXG
pd download SCSZUyXG -o ./file.zip

# View file details
pd info https://pixeldrain.com/u/SCSZUyXG
pd info SCSZUyXG

# Upload a file (requires API key)
pd upload ./ROM.zip
pd upload ./ROM.zip -k <api_key>

# List files in album
pd list <list_id>

# Delete a file
pd delete <file_id> -k <api_key>
```

### Pixeldrain Python Library Usage
```python
from pixeldrain import PixelDrainClient

client = PixelDrainClient(api_key="<api_key>")

# Info
item = client.info("SCSZUyXG")
print(f"{item.name} - {item.size} bytes (SHA256: {item.sha256_hash})")

# Download
dest = client.download("SCSZUyXG", output_path="./AGENTS.md", concurrency=4)

# Upload
res = client.upload("./ROM.zip")
print(f"Uploaded: {res.url} (ID: {res.id})")
```

---

## Telegram CLI & Library

A client and CLI for Telegram notifications, live progress streaming (`editMessageText`), and interactive multi-cloud bot integration.
Entrypoints: `telegram` and `tg`.

### Telegram CLI Usage
```bash
# Configure Telegram credentials
tg config set --token <BOT_TOKEN> --chat-id <CHAT_ID>

# Verify bot connectivity and test ping
tg test

# Send one-off notification
tg send "Transfer complete!"

# Start interactive bot daemon
tg bot

# Stream progress and alerts from any cloud transfer CLI:
sf download rom/lineage.zip -p myproject -n
gf upload ./video.mp4 -n
pd download SCSZUyXG -n
vf upload ./file.zip -n
```

### Telegram Python Library Usage
```python
from telegram import TelegramClient, TelegramProgressReporter

# Send message
client = TelegramClient(bot_token="<token>", chat_id="<chat_id>")
client.send_message("<b>Transfer completed successfully!</b>")

# Live throttled progress streaming
reporter = TelegramProgressReporter(
    title="ROM.zip", client=client, target_name="GoFile"
)
reporter.advance(1024 * 1024 * 10, total_bytes=1024 * 1024 * 100)
reporter.finish(success_url="https://gofile.io/d/xyz")
```
