from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from pixeldrain.api import (
    extract_file_id,
    get_auth_headers,
    get_file_info,
)
from pixeldrain.cli import cli
from pixeldrain.client import PixelDrainClient
from pixeldrain.config import Config, format_size


def test_extract_file_id():
    assert extract_file_id("https://pixeldrain.com/u/SCSZUyXG") == "SCSZUyXG"
    assert extract_file_id("https://pixeldrain.com/api/file/SCSZUyXG") == "SCSZUyXG"
    assert extract_file_id("SCSZUyXG") == "SCSZUyXG"


def test_get_auth_headers():
    h_none = get_auth_headers(None)
    assert "Authorization" not in h_none
    h_key = get_auth_headers("my_secret_key")
    assert "Authorization" in h_key
    assert h_key["Authorization"].startswith("Basic ")


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1048576 * 5) == "5.0 MB"


def test_pixeldrain_config_save_and_load(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg_file = tmp_path / "config.toml"
        monkeypatch.setattr("pixeldrain.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("pixeldrain.config.CONFIG_FILE", cfg_file)

        cfg = Config(
            api_key="pd_api_key_123",
            concurrency=8,
            chunk_size=4 * 1024 * 1024,
        )
        cfg.save()

        loaded = Config.load()
        assert loaded.api_key == "pd_api_key_123"
        assert loaded.concurrency == 8
        assert loaded.chunk_size == 4 * 1024 * 1024


def test_pixeldrain_get_file_info_live():
    info = get_file_info("SCSZUyXG")
    assert info is not None
    assert info.id == "SCSZUyXG"
    assert info.name == "AGENTS.md"
    assert info.size == 6508
    assert (
        info.sha256_hash
        == "fdb61972e4dbcd40cc57476b05cbc54b73a8b2032963831abda6a9147cb38db2"
    )
    assert info.can_download is True


def test_pixeldrain_download_and_verify_live():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = PixelDrainClient()
        dest_path = Path(tmpdir) / "test_agents.md"
        try:
            dest = client.download(
                "SCSZUyXG", output_path=dest_path, concurrency=2, verify_checksum=True
            )
            assert dest.is_file()
            assert dest.stat().st_size == 6508
            text = dest.read_text(encoding="utf-8")
            assert "Panduan" in text
        except RuntimeError as e:
            if "403" in str(e) or "rate_limited" in str(e):
                pytest.skip("Pixeldrain public rate limit / captcha required")
            raise


def test_pixeldrain_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Pixeldrain CLI" in result.output
    assert "download" in result.output
    assert "upload" in result.output
    assert "info" in result.output


def test_pixeldrain_cli_info_live():
    runner = CliRunner()
    result = runner.invoke(cli, ["info", "SCSZUyXG"])
    assert result.exit_code == 0
    assert "AGENTS.md" in result.output
    assert "SCSZUyXG" in result.output
    assert (
        "fdb61972e4dbcd40cc57476b05cbc54b73a8b2032963831abda6a9147cb38db2"
        in result.output
    )


def test_pixeldrain_cli_interrupt():
    runner = CliRunner()
    with patch(
        "pixeldrain.client.PixelDrainClient.download", side_effect=KeyboardInterrupt
    ):
        result = runner.invoke(cli, ["download", "SCSZUyXG"])
        assert result.exit_code == 130
        assert "Operation cancelled by user" in result.output
