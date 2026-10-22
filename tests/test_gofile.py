from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from gofile.api import (
    generate_website_token,
    get_content_id,
    parse_content_items,
)
from gofile.cli import cli
from gofile.config import Config


def test_get_content_id():
    assert get_content_id("https://gofile.io/d/yt9wik0T") == "yt9wik0T"
    assert get_content_id("https://gofile.io/d/yt9wik0T/") == "yt9wik0T"
    assert get_content_id("yt9wik0T") == "yt9wik0T"
    assert (
        get_content_id("https://gofile.io/d/c3b7f793-f120-4dd2-abd3-91eea5914d4a")
        == "c3b7f793-f120-4dd2-abd3-91eea5914d4a"
    )


def test_generate_website_token():
    token = "test_token_123"
    wt = generate_website_token(token)
    assert len(wt) == 64  # SHA256 hex length
    assert all(c in "0123456789abcdef" for c in wt)


def test_gofile_config_save_and_load(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg_file = tmp_path / "config.toml"
        monkeypatch.setattr("gofile.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("gofile.config.CONFIG_FILE", cfg_file)

        cfg = Config(
            token="gf_secret_token",
            account_id="acc_123",
            root_folder="root_456",
            concurrency=8,
            chunk_size=4 * 1024 * 1024,
        )
        cfg.save()

        loaded = Config.load()
        assert loaded.token == "gf_secret_token"
        assert loaded.account_id == "acc_123"
        assert loaded.root_folder == "root_456"
        assert loaded.concurrency == 8
        assert loaded.chunk_size == 4 * 1024 * 1024


def test_parse_content_items_folder():
    data = {
        "id": "folder_1",
        "name": "MyFolder",
        "type": "folder",
        "children": {
            "child_1": {
                "id": "child_1",
                "name": "file1.zip",
                "type": "file",
                "size": 1048576,
                "link": "https://s.gofile.io/download/file1.zip",
                "md5": "d41d8cd98f00b204e9800998ecf8427e",
            },
            "child_2": {
                "id": "child_2",
                "name": "subfolder",
                "type": "folder",
                "size": 0,
            },
        },
    }
    items = parse_content_items(data)
    assert len(items) == 2
    # Sorted: directories first, then files
    assert items[0].name == "subfolder"
    assert items[0].is_dir is True
    assert items[1].name == "file1.zip"
    assert items[1].size == 1048576
    assert items[1].is_dir is False


def test_parse_content_items_single_file():
    data = {
        "id": "file_solo",
        "name": "solo.tar.gz",
        "type": "file",
        "size": 2048,
        "link": "https://s.gofile.io/download/solo.tar.gz",
        "md5": "abc123md5",
    }
    items = parse_content_items(data)
    assert len(items) == 1
    assert items[0].name == "solo.tar.gz"
    assert items[0].is_dir is False
    assert items[0].link == "https://s.gofile.io/download/solo.tar.gz"


def test_gofile_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "GoFile CLI" in result.output
    assert "download" in result.output
    assert "upload" in result.output
    assert "list" in result.output
    assert "config" in result.output


def test_gofile_cli_interrupt():
    runner = CliRunner()
    with patch("gofile.client.GoFileClient.download", side_effect=KeyboardInterrupt):
        result = runner.invoke(cli, ["download", "https://gofile.io/d/fake123"])
        assert result.exit_code == 130
        assert "Operation cancelled by user" in result.output
