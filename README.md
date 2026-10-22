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
# View configuration
sf config show

# Set default project, username, or mirror
sf config set -p <project> -u <username> -k ~/.ssh/id_ed25519
sf config set --pick-mirror
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
client.download("rom/README.md", output_path="README.md", mirror="master", concurrency=4)

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
