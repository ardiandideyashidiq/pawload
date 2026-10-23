# pawload (WIP)

Multi-cloud transfer CLI, scraper, and web dashboard for **SourceForge**, **GoFile**, **PixelDrain**, **VikingFile**, and **Telegram**.
---

## Installation

```bash
# Install CLI globally via uv:
uv tool install git+https://github.com/ardiandideyashidiq/pawload.git

# Or add as dependency to a project:
uv add git+https://github.com/ardiandideyashidiq/pawload.git
```

Installed entrypoints: `pawload`, `pl`, `web` (plus individual `sf`, `gf`, `pd`, `vf`, `tg`).

---

## Quick Setup

Run the interactive setup wizard to configure credentials and defaults:
```bash
pawload setup
```
Configuration is stored at `~/.config/pawload/config.toml` (override via `PAWLOAD_CONFIG`).

```bash
# View active configuration
pawload config show
```

---

## CLI Usage

### Unified Commands
```bash
# Upload to any provider
pawload gofile upload archive.tar.gz
pawload sourceforge upload firmware.zip -d release
pawload pixeldrain upload image.png
pawload vikingfile upload document.pdf

# Shorthand aliases work identically:
pl gf upload archive.tar.gz
pl sf upload firmware.zip -d release
pl pd upload image.png
pl vf upload document.pdf

# Download with parallel chunks and resume support
pawload sourceforge download <project>/<path>
pawload gofile download https://gofile.io/d/<id>
pawload pixeldrain download <file_id>
pawload vikingfile download <direct_url>
```

### Web GUI Dashboard
Launch the embedded local web interface (Flask + React / Tailwind CSS):
```bash
pawload web
# or
web
```
Accessible at `http://127.0.0.1:8765`.

---

## Python SDK Integration

```python
import pawload

# Auto-detects provider and downloads with parallel chunks
path = pawload.download("https://gofile.io/d/abc123", output_path="./downloads/")

# Upload directly to SourceForge, GoFile, PixelDrain, or VikingFile
remote_path = pawload.upload(
    "build/app-v1.0.zip",
    provider="sourceforge",
    project="my-project",
    remote_dir="release",
    force=True,
)

# Direct provider clients:
from pawload import SourceForgeClient, GoFileClient, PixelDrainClient, VikingFileClient

sf = SourceForgeClient(project="my-project")
files = sf.list(remote_dir="release")
```

Full SDK documentation is available in [docs/API.md](docs/API.md).
