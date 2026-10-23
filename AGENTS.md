# Repository Guidelines

Comprehensive developer guidelines, architecture overview, and code conventions for the **Pawload** codebase.

---

## Project Overview

**Pawload** is a Python 3.13+ multi-cloud file transfer CLI, scraper, and web dashboard. It supports parallel chunked downloads (with stateful resume), streaming uploads, remote file management, and progress reporting across multiple cloud storage providers:
- **SourceForge**: FRS file management, native SFTP uploads, live mirror probe/selection, and chunked downloads with RSS checksum verification.
- **GoFile**: Chunked multipart streaming uploads, folder browsing, guest token windowing, and multi-threaded downloads.
- **PixelDrain**: Direct uploads, chunked downloads, metadata checks, and list management.
- **VikingFile**: Account/anonymous file uploads, direct chunked downloads, and file checks.
- **Telegram**: Real-time progress reporter (`TelegramProgressReporter`) and interactive bot runner (`aiogram`).
- **Web GUI**: Embedded Flask backend with Server-Sent Events (SSE) streaming and a React 19 / Tailwind CSS v4 dashboard.

---

## Architecture & Data Flow

```
                      ┌──────────────────────────────────────┐
                      │    Unified SDK / CLI (pawload)       │
                      │  detect_provider(), upload/download  │
                      └──────────────────┬───────────────────┘
                                         │
        ┌───────────────┬────────────────┼────────────────┬────────────────┐
        ▼               ▼                ▼                ▼                ▼
┌───────────────┐┌──────────────┐┌──────────────┐┌───────────────┐ ┌───────────────┐
│  sourceforge  ││    gofile    ││  pixeldrain  ││  vikingfile   │ │   telegram    │
│  (SFTP, HTTP) ││ (REST HTTP)  ││ (REST HTTP)  ││  (REST HTTP)  │ │(aiogram, REST)│
└───────┬───────┘└──────┬───────┘└──────┬───────┘└──────┬────────┘ └───────┬───────┘
        └───────────────┼────────────────┼──────────────┼──────────────────┘
                        ▼                ▼              ▼
                      ┌──────────────────────────────────────┐
                      │          web / GUI Bridge            │
                      │  AsyncLoopThread, Flask REST & SSE   │
                      └──────────────────────────────────────┘
                                         │ (SSE + REST)
                                         ▼
                      ┌──────────────────────────────────────┐
                      │      Frontend (React 19 / Vite)      │
                      └──────────────────────────────────────┘
```

### High-Level Data Flows
1. **Unified Upload Pipeline**:
   - `pawload.upload()` / CLI invokes provider client (`SourceForgeClient`, `GoFileClient`, etc.).
   - Uploaders stream payloads in chunks using `CurlOpt.READFUNCTION` / `asyncssh` and notify `progress_callback(completed, total)`.
   - `TelegramProgressReporter` throttles updates (`throttle_interval = 2.0s`) and edits status messages on Telegram.
2. **Parallel Chunked Download Pipeline**:
   - Provider determines file size and range support via HTTP HEAD/GET (`accept-ranges: bytes`).
   - Sparse destination file is created on disk (`dest_file.truncate(total_bytes)`).
   - Concurrency workers grab chunk offsets from an `asyncio.Queue` and write concurrently at mapped offsets (`dest_file.seek(offset)`).
   - Progress is persisted into `<file>.sfdownload` / `<file>.<provider>download` sidecars for instant resume after interruptions.
3. **Web GUI SSE Event Pipeline**:
   - Background transfers run inside a dedicated loop thread (`AsyncLoopThread`).
   - Events (`transfer_added`, `transfer_progress`, `transfer_completed`, `transfer_error`) pass through `WebBridge.dispatch_event()`.
   - Flask streams events to `/api/events` via `stream_with_context` to the React `useTransfers` hook.

---

## Key Directories

```
.
├── src/
│   ├── pawload/        # Top-level unified SDK facade, API dispatch, and CLI group
│   ├── sourceforge/    # SourceForge SFTP client, mirror probing, RSS parser, chunked downloader
│   ├── gofile/         # GoFile REST client, token management, chunked downloader, streaming uploader
│   ├── pixeldrain/     # PixelDrain client, uploader, chunked downloader, API helpers
│   ├── vikingfile/     # VikingFile client, uploader, chunked downloader, API helpers
│   ├── telegram/       # Telegram Bot client (curl_cffi), reporter, aiogram bot daemon
│   └── web/            # Flask REST API, WebBridge background runner, and embedded dist/ assets
├── frontend/           # React 19, TypeScript, Tailwind CSS v4, Radix UI single-page application
├── tests/              # Pytest test suite covering SDK, providers, web bridge, and CLI commands
└── docs/               # Technical documentation and SDK API reference (docs/API.md)
```

---

## Development Commands

### Backend (Python & UV)
```bash
# Install dependencies into virtual environment
uv sync

# Run the complete test suite
uv run pytest

# Run a specific test file or test case
uv run pytest tests/test_sdk.py
uv run pytest tests/test_sdk.py::test_unified_upload_dispatch

# Lint codebase
uv run ruff check .

# Execute unified CLI
uv run pawload --help
uv run pl <subcommand>

# Start the web GUI server (default http://127.0.0.1:8765)
uv run pawload web serve --host 0.0.0.0 --port 8765 --no-browser
# or shortcut:
uv run web
```

### Frontend (Bun & Vite)
```bash
cd frontend

# Install frontend dependencies
bun install

# Run Vite dev server with proxy to backend (http://localhost:5173 -> http://127.0.0.1:8765)
bun run dev

# Run frontend linter
bun run lint

# Build production bundle (outputs to ../src/web/dist/)
bun run build
```

---

## Code Conventions & Common Patterns

### 1. Dual Sync/Async Parity (`_run_sync`)
Every client method has both synchronous and asynchronous forms (`upload` / `upload_async`, `download` / `download_async`). Re-entrant synchronous execution avoids event-loop collisions:
```python
def _run_sync(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)
```

### 2. Provider Auto-Detection
Target strings and URLs are mapped to appropriate providers via `detect_provider(target)`:
- `gf:<id>` or `*gofile.io*` -> `gofile`
- `pd:<id>` or `*pixeldrain.com*` -> `pixeldrain`
- `vf:<hash>` or `*vikingfile.com*` -> `vikingfile`
- `sf:<proj>/<path>`, `*sourceforge.net*`, or `<proj>/<path>` -> `sourceforge`

### 3. File Descriptor & Worker Safety
When coordinating parallel download workers with `asyncio.gather(*tasks)`:
- Always wrap in `try...except...finally` blocks.
- Cancel pending workers on failure and await cancellation: `await asyncio.gather(*tasks, return_exceptions=True)`.
- Always flush and close destination file descriptors in the `finally:` block.

### 4. Progress Reporting Signatures
- Progress callbacks follow `(completed_bytes: int, total_bytes: int) -> None`.
- High-level listeners accumulate progress monotonically without flickering back to 0.

### 5. Standard ASCII Status Tags
Console and Telegram message outputs use standardized bracketed ASCII tags:
- Success: `[OK]`
- Errors: `[ERROR]`
- Warnings: `[WARN]`
- Info: `[INFO]`
- Network: `[UPLOAD]`, `[DOWNLOAD]`, `[PING]`, `[TRANSFER]`

---

## Important Files

- `src/pawload/__init__.py`: Public SDK root exporting clients (`SourceForgeClient`, `GoFileClient`, etc.) and top-level transfer functions (`upload`, `download`).
- `src/pawload/api.py`: Provider auto-detection and high-level sync/async upload/download dispatchers.
- `src/pawload/cli.py`: Click command group with shorthand aliases (`gf`, `sf`, `pd`, `vf`, `tg`, `gui`) and interactive `pawload setup`.
- `src/sourceforge/config.py`: Unified TOML configuration resolver (`get_unified_config_file()`, `load_section()`, `save_section()`).
- `src/web/bridge.py`: `WebBridge` orchestrating transfers between Flask, provider coroutines, and SSE subscribers.
- `src/web/app.py`: Flask app factory, REST API endpoints, and static SPA serving.
- `frontend/src/App.tsx`: Top-level React dashboard state and layout.
- `pyproject.toml`: Hatchling package definitions, dependencies, and CLI script entrypoints.
- `docs/API.md`: Comprehensive Python SDK documentation and usage guide.

---

## Runtime & Tooling Preferences

- **Python Runtime**: Python `>= 3.13`. Package management via `uv`.
- **Node / Frontend Tooling**: **Bun** is the designated package manager and runner (`bun.lock`, `bun run build`).
- **Configuration Precedence**:
  1. `PAWLOAD_CONFIG` environment variable (or `CONFIG_FILE`).
  2. `~/.config/pawload/config.toml` (via `$XDG_CONFIG_HOME`).
  *(Legacy paths and environment variables like `SCRAPER_CONFIG`, `MULTICLOUD_CONFIG`, and `~/.config/scraper/` are deprecated).*

---

## Testing & QA

- **Framework**: `pytest>=9.1.1`.
- **Execution Pattern**: Run all tests via `uv run pytest`.
- **Mocking**:
  - Network requests mocked via `unittest.mock.patch("curl_cffi.requests.post")` / `.get`.
  - Coroutines mocked via `AsyncMock`.
  - CLI subcommands tested via `click.testing.CliRunner`.
  - Asynchronous functions tested inside regular test functions using `asyncio.run()`.
- **Pre-commit / Verification Expectation**:
  - All 64 tests in `tests/` must pass cleanly without network flakiness.
  - When editing `frontend/`, always re-run `bun run build` inside `frontend/` to keep `src/web/dist` in sync with TypeScript source files.
