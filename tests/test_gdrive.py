from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from gdrive.api import (
    GDriveItem,
    extract_filename_from_cd,
    extract_gdrive_id,
    load_cookies,
    resolve_direct_download,
)
from gdrive.cli import cli
from gdrive.client import GDriveClient
from gdrive.config import Config


def test_extract_gdrive_id():
    assert (
        extract_gdrive_id("https://drive.google.com/open?id=1mcRTM4UuJm31mt0RzS18Z3_KsAK2Mv2x")
        == "1mcRTM4UuJm31mt0RzS18Z3_KsAK2Mv2x"
    )
    assert (
        extract_gdrive_id("https://drive.google.com/file/d/12asPt3gTnvJNdiusf225ey_rOhuHskhE/view?usp=sharing")
        == "12asPt3gTnvJNdiusf225ey_rOhuHskhE"
    )
    assert (
        extract_gdrive_id("https://drive.google.com/drive/folders/1mcRTM4UuJm31mt0RzS18Z3_KsAK2Mv2x")
        == "1mcRTM4UuJm31mt0RzS18Z3_KsAK2Mv2x"
    )
    assert extract_gdrive_id("gd:12asPt3gTnvJNdiusf225ey_rOhuHskhE") == "12asPt3gTnvJNdiusf225ey_rOhuHskhE"
    assert extract_gdrive_id("gdrive:12asPt3gTnvJNdiusf225ey_rOhuHskhE") == "12asPt3gTnvJNdiusf225ey_rOhuHskhE"
    assert extract_gdrive_id("12asPt3gTnvJNdiusf225ey_rOhuHskhE") == "12asPt3gTnvJNdiusf225ey_rOhuHskhE"


def test_extract_filename_from_cd():
    assert extract_filename_from_cd('attachment; filename="archive.zip"') == "archive.zip"
    assert extract_filename_from_cd("attachment; filename=test.tar.gz") == "test.tar.gz"
    assert extract_filename_from_cd("attachment; filename*=UTF-8''encoded%20name.zip") == "encoded name.zip"
    assert extract_filename_from_cd("") is None


def test_load_cookies_from_netscape(tmp_path: Path):
    cookie_file = tmp_path / "test_cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".google.com\tTRUE\t/\tTRUE\t1900000000\tTEST_COOKIE\tsecret_val\n"
    )
    cookies = load_cookies(cookie_file)
    assert cookies.get("TEST_COOKIE") == "secret_val"


def test_gdrive_config_save_and_load(tmp_path: Path, monkeypatch):
    import gdrive.config as gd_cfg
    import sourceforge.config as sf_cfg

    cfg_file = tmp_path / "gdrive_test_cfg.toml"
    monkeypatch.setattr(sf_cfg, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(gd_cfg, "CONFIG_FILE", cfg_file)

    cfg = Config(cookie_file="custom_cookie.txt", concurrency=8, chunk_size=4 * 1024 * 1024)
    cfg.save()

    loaded = Config.load()
    assert loaded.cookie_file == "custom_cookie.txt"
    assert loaded.concurrency == 8
    assert loaded.chunk_size == 4 * 1024 * 1024


def test_resolve_direct_download_flow():
    mock_resp1 = AsyncMock()
    mock_resp1.status_code = 303
    mock_resp1.headers = {"location": "https://drive.usercontent.google.com/download?id=test&export=download&authuser=0"}

    async def aiter_content_mock():
        yield (
            b'<form id="download-form" action="https://drive.usercontent.google.com/download" method="get">'
            b'<input type="hidden" name="id" value="test">'
            b'<input type="hidden" name="export" value="download">'
            b'<input type="hidden" name="confirm" value="t">'
            b'<input type="hidden" name="uuid" value="12345">'
            b'</form>'
        )

    mock_resp2 = AsyncMock()
    mock_resp2.status_code = 200
    mock_resp2.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp2.aiter_content = aiter_content_mock

    mock_resp3 = AsyncMock()
    mock_resp3.status_code = 206
    mock_resp3.headers = {
        "content-type": "application/octet-stream",
        "content-disposition": 'attachment; filename="test_pkg.zip"',
        "content-range": "bytes 0-0/1048576",
        "content-length": "1048576",
    }

    mock_session = AsyncMock()
    mock_session.get.side_effect = [mock_resp1, mock_resp2, mock_resp3, mock_resp3]
    url, fn, sz = asyncio.run(resolve_direct_download("test", session=mock_session))
    assert "confirm=t" in url
    assert "uuid=12345" in url
    assert fn == "test_pkg.zip"
    assert sz == 1048576


def test_gdrive_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Google Drive CLI" in result.output
    assert "info" in result.output
    assert "url" in result.output
    assert "list" in result.output
    assert "download" in result.output
    assert "config" in result.output


def test_gdrive_cli_info_mocked():
    runner = CliRunner()
    mock_item = GDriveItem(
        id="test_id_123",
        name="test_file.zip",
        size=1048576,
        is_folder=False,
        direct_url="https://drive.usercontent.google.com/download?id=test",
    )
    with patch("gdrive.client.GDriveClient.info", return_value=mock_item):
        result = runner.invoke(cli, ["info", "test_id_123"])
        assert result.exit_code == 0
        assert "test_id_123" in result.output
        assert "test_file.zip" in result.output
        assert "1.0 MB" in result.output


def test_gdrive_cli_url_mocked():
    runner = CliRunner()
    with patch(
        "gdrive.client.GDriveClient.get_direct_url",
        return_value=("https://drive.usercontent.google.com/direct_link", "test_file.zip", 2048),
    ):
        result = runner.invoke(cli, ["url", "test_id_123"])
        assert result.exit_code == 0
        assert "test_file.zip" in result.output
        assert "https://drive.usercontent.google.com/direct_link" in result.output


def test_gdrive_cli_config_commands(tmp_path: Path, monkeypatch):
    import gdrive.config as gd_cfg
    import sourceforge.config as sf_cfg

    cfg_file = tmp_path / "gdrive_cli_cfg.toml"
    monkeypatch.setattr(sf_cfg, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(gd_cfg, "CONFIG_FILE", cfg_file)

    runner = CliRunner()
    res_set = runner.invoke(cli, ["config", "set", "--cookie-file", "cookie.txt", "--concurrency", "6"])
    assert res_set.exit_code == 0
    assert "Configuration saved" in res_set.output

    res_show = runner.invoke(cli, ["config", "show"])
    assert res_show.exit_code == 0
    assert "cookie.txt" in res_show.output
    assert "6" in res_show.output


def test_gdrive_client_download_mocked(tmp_path: Path):
    dummy_out = tmp_path / "out.zip"
    client = GDriveClient()
    with patch("gdrive.client.download_file_async", new_callable=AsyncMock) as mock_dl:
        mock_dl.return_value = dummy_out
        res = client.download("gd:test_file", output_path=dummy_out)
        assert res == dummy_out
        mock_dl.assert_called_once()
