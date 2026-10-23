from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

import pawload
from pawload import (
    GoFileClient,
    PixelDrainClient,
    SourceForgeClient,
    TelegramClient,
    VikingFileClient,
    detect_provider,
    download,
    download_async,
    fetch_live_mirrors,
    open_sftp,
    parse_target,
    upload,
    upload_async,
)


def test_sdk_imports():
    """Verify that all core symbols can be imported directly from the top-level pawload package."""
    assert pawload.SourceForgeClient is SourceForgeClient
    assert pawload.GoFileClient is GoFileClient
    assert pawload.PixelDrainClient is PixelDrainClient
    assert pawload.VikingFileClient is VikingFileClient
    assert pawload.TelegramClient is TelegramClient
    assert callable(pawload.upload)
    assert callable(pawload.download)
    assert callable(pawload.upload_async)
    assert callable(pawload.download_async)
    assert callable(fetch_live_mirrors)
    assert callable(parse_target)
    assert callable(open_sftp)


def test_detect_provider():
    assert detect_provider("https://gofile.io/d/abc1234") == "gofile"
    assert detect_provider("gf:abc1234") == "gofile"
    assert detect_provider("https://pixeldrain.com/u/xyz999") == "pixeldrain"
    assert detect_provider("pd:xyz999") == "pixeldrain"
    assert detect_provider("https://vikingfile.com/f/hash123") == "vikingfile"
    assert detect_provider("vf:hash123") == "vikingfile"
    assert detect_provider("https://downloads.sourceforge.net/project/p/f.zip") == "sourceforge"
    assert detect_provider("sf:myproject/release/app.exe") == "sourceforge"
    assert detect_provider("myproject/release/app.exe") == "sourceforge"


def test_unified_upload_dispatch(tmp_path: Path):
    dummy_file = tmp_path / "test_artifact.bin"
    dummy_file.write_bytes(b"hello sdk")

    # Test SourceForge upload dispatch
    with patch("sourceforge.client.SourceForgeClient.upload_async", new_callable=AsyncMock) as mock_sf:
        mock_sf.return_value = "/home/frs/project/proj/test_artifact.bin"
        res = upload(dummy_file, provider="sourceforge", project="proj", remote_path="release")
        assert res == "/home/frs/project/proj/test_artifact.bin"
        mock_sf.assert_called_once()

    # Test GoFile upload dispatch
    with patch("gofile.client.GoFileClient.upload_async", new_callable=AsyncMock) as mock_gf:
        mock_gf.return_value = "https://gofile.io/d/test123"
        res = upload(dummy_file, provider="gofile", token="tok123")
        assert res == "https://gofile.io/d/test123"
        mock_gf.assert_called_once()

    # Test Pixeldrain upload dispatch
    with patch("pixeldrain.client.PixelDrainClient.upload_async", new_callable=AsyncMock) as mock_pd:
        mock_pd.return_value = "https://pixeldrain.com/u/pd123"
        res = upload(dummy_file, provider="pixeldrain", api_key="key123")
        assert res == "https://pixeldrain.com/u/pd123"
        mock_pd.assert_called_once()

    # Test VikingFile upload dispatch
    with patch("vikingfile.client.VikingFileClient.upload_async", new_callable=AsyncMock) as mock_vf:
        mock_vf.return_value = "https://vikingfile.com/f/vf123"
        res = upload(dummy_file, provider="vikingfile", user="userhash")
        assert res == "https://vikingfile.com/f/vf123"
        mock_vf.assert_called_once()


def test_unified_async_upload(tmp_path: Path):
    import asyncio

    dummy_file = tmp_path / "test_async.bin"
    dummy_file.write_bytes(b"async content")

    with patch("gofile.client.GoFileClient.upload_async", new_callable=AsyncMock) as mock_gf:
        mock_gf.return_value = "https://gofile.io/d/async123"
        res = asyncio.run(upload_async(dummy_file, provider="gofile"))
        assert res == "https://gofile.io/d/async123"

def test_unified_download_dispatch(tmp_path: Path):
    out_file = tmp_path / "out.bin"

    # Auto-detect SourceForge
    with patch("sourceforge.client.SourceForgeClient.download_async", new_callable=AsyncMock) as mock_sf:
        mock_sf.return_value = out_file
        res = download("sf:proj/release/out.bin", output_path=out_file)
        assert res == out_file
        mock_sf.assert_called_once()

    # Auto-detect GoFile
    with patch("gofile.client.GoFileClient.download_async", new_callable=AsyncMock) as mock_gf:
        mock_gf.return_value = out_file
        res = download("https://gofile.io/d/fake123", output_path=out_file)
        assert res == out_file
        mock_gf.assert_called_once()

    # Auto-detect Pixeldrain
    with patch("pixeldrain.client.PixelDrainClient.download_async", new_callable=AsyncMock) as mock_pd:
        mock_pd.return_value = out_file
        res = download("https://pixeldrain.com/u/test123", output_path=out_file)
        assert res == out_file
        mock_pd.assert_called_once()

    # Auto-detect VikingFile
    with patch("vikingfile.client.VikingFileClient.download_async", new_callable=AsyncMock) as mock_vf:
        mock_vf.return_value = out_file
        res = download("https://vikingfile.com/f/hash123", output_path=out_file)
        assert res == out_file
        mock_vf.assert_called_once()


def test_unified_async_download(tmp_path: Path):
    import asyncio

    out_file = tmp_path / "async_out.bin"

    with patch("gofile.client.GoFileClient.download_async", new_callable=AsyncMock) as mock_gf:
        mock_gf.return_value = out_file
        res = asyncio.run(download_async("https://gofile.io/d/async_test", output_path=out_file))
        assert res == out_file
