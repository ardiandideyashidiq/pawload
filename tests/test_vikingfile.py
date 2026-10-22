from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from vikingfile.api import (
    check_file,
    extract_file_hash,
    get_upload_server,
)
from vikingfile.cli import cli
from vikingfile.config import Config, format_size


def test_extract_file_hash():
    assert extract_file_hash("https://vikingfile.com/f/QL0UByzja9") == "QL0UByzja9"
    assert extract_file_hash("https://vik1ngfile.site/f/QL0UByzja9/") == "QL0UByzja9"
    assert extract_file_hash("QL0UByzja9") == "QL0UByzja9"


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(500) == "500 B"
    assert format_size(1024) == "1.0 KB"


def test_vikingfile_config_save_and_load(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg_file = tmp_path / "config.toml"
        monkeypatch.setattr("vikingfile.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("vikingfile.config.CONFIG_FILE", cfg_file)

        cfg = Config(
            user="user_hash_123",
            concurrency=8,
            chunk_size=4 * 1024 * 1024,
        )
        cfg.save()

        loaded = Config.load()
        assert loaded.user == "user_hash_123"
        assert loaded.concurrency == 8
        assert loaded.chunk_size == 4 * 1024 * 1024


def test_vikingfile_get_server_live():
    server = get_upload_server()
    assert server.startswith("https://")
    assert "vikingfile" in server


def test_vikingfile_check_file_live():
    info = check_file("QL0UByzja9")
    assert info is not None
    assert info.exist is True
    assert info.name == "AGENTS.md"
    assert info.size > 0
    assert info.hash == "QL0UByzja9"


def test_vikingfile_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "VikingFile CLI" in result.output
    assert "upload" in result.output
    assert "check" in result.output
    assert "download" in result.output


def test_vikingfile_cli_check_command_live():
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "QL0UByzja9"])
    assert result.exit_code == 0
    assert "AGENTS.md" in result.output
    assert "QL0UByzja9" in result.output


def test_vikingfile_cli_interrupt():
    runner = CliRunner()
    with patch("vikingfile.client.VikingFileClient.upload", side_effect=KeyboardInterrupt):
        result = runner.invoke(cli, ["upload", "README.md"])
        assert result.exit_code == 130
        assert "Operation cancelled by user" in result.output
