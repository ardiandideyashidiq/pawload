from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gofile.client import GoFileClient
from pixeldrain.client import PixelDrainClient
from sourceforge.client import SourceForgeClient
from vikingfile.client import VikingFileClient

__all__ = [
    "detect_provider",
    "download",
    "download_async",
    "upload",
    "upload_async",
]


def detect_provider(target: str) -> str:
    """Infer cloud provider identifier from target URL or shorthand prefix."""
    clean = target.strip()
    if clean.startswith("gf:") or "gofile.io" in clean:
        return "gofile"
    if clean.startswith("pd:") or "pixeldrain.com" in clean:
        return "pixeldrain"
    if clean.startswith("vf:") or "vikingfile.com" in clean or "vik1ngfile.com" in clean:
        return "vikingfile"
    if (
        clean.startswith("sf:")
        or "sourceforge.net" in clean
        or "fsdn.com" in clean
        or ("/" in clean and not clean.startswith(("http://", "https://")))
    ):
        return "sourceforge"
    return "unknown"


def _run_sync(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


async def upload_async(
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
) -> Any:
    """Upload a file asynchronously to the selected provider."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Local file not found: {file_path}")

    prov = provider.lower().strip()

    if prov in ("sourceforge", "sf"):
        sf = SourceForgeClient(
            project=project,
            username=username,
            key_path=key_path,
        )
        remote_file = await sf.upload_async(
            local_path=path,
            remote_dir=remote_path,
            force=force,
            interactive=False,
            progress_callback=progress_callback,
        )
        return remote_file

    if prov in ("gofile", "gf"):
        gf = GoFileClient(token=token)
        return await gf.upload_async(
            file_path=path,
            folder_id=remote_path or None,
            progress_callback=progress_callback,
        )

    if prov in ("pixeldrain", "pd"):
        pd = PixelDrainClient(api_key=api_key)
        return await pd.upload_async(
            file_path=path,
            progress_callback=progress_callback,
        )

    if prov in ("vikingfile", "vf"):
        vf = VikingFileClient(user=user)
        return await vf.upload_async(
            file_path=path,
            remote_path=remote_path,
            progress_callback=progress_callback,
        )

    raise ValueError(f"Unknown upload provider: '{provider}'")


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
) -> Any:
    """Upload a file synchronously to the selected provider."""
    return _run_sync(
        upload_async(
            file_path=file_path,
            provider=provider,
            remote_path=remote_path,
            project=project,
            username=username,
            key_path=key_path,
            token=token,
            api_key=api_key,
            user=user,
            force=force,
            progress_callback=progress_callback,
        )
    )


async def download_async(
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
) -> Path:
    """Download a file asynchronously with automatic provider detection."""
    prov = (provider or detect_provider(target)).lower().strip()

    if prov in ("sourceforge", "sf"):
        sf = SourceForgeClient(project=project)
        return await sf.download_async(
            target=target,
            output_path=output_path,
            mirror=mirror,
            concurrency=concurrency,
            verify_checksum=verify_checksum,
            interactive_prompt=False,
            progress_callback=progress_callback,
        )

    if prov in ("gofile", "gf"):
        gf = GoFileClient(token=token, concurrency=concurrency)
        res = await gf.download_async(
            target=target,
            output_path=output_path,
            verify_checksum=verify_checksum,
            progress_callback=progress_callback,
        )
        return res[0] if isinstance(res, list) else res

    if prov in ("pixeldrain", "pd"):
        pd = PixelDrainClient(api_key=api_key, concurrency=concurrency)
        return await pd.download_async(
            target=target,
            output_path=output_path,
            verify_checksum=verify_checksum,
            progress_callback=progress_callback,
        )

    if prov in ("vikingfile", "vf"):
        vf = VikingFileClient()
        return await vf.download_async(
            target=target,
            output_path=output_path,
            concurrency=concurrency,
            progress_callback=progress_callback,
        )

    raise ValueError(f"Could not determine download provider for target: '{target}'")


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
) -> Path:
    """Download a file synchronously with automatic provider detection."""
    return _run_sync(
        download_async(
            target=target,
            output_path=output_path,
            provider=provider,
            project=project,
            mirror=mirror,
            concurrency=concurrency,
            verify_checksum=verify_checksum,
            token=token,
            api_key=api_key,
            progress_callback=progress_callback,
        )
    )
