from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from telegram.cli import cli
from telegram.client import TelegramClient
from telegram.config import Config
from telegram.reporter import (
    TelegramProgressReporter,
    create_reporter,
    format_size,
    format_time,
    render_bar,
)


def test_telegram_config(tmp_path, monkeypatch):
    test_conf = tmp_path / "config.toml"
    monkeypatch.setattr("telegram.config.CONFIG_FILE", test_conf)
    monkeypatch.setattr("telegram.config.CONFIG_DIR", tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    cfg = Config.load()
    assert cfg.bot_token is None

    cfg.bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    cfg.chat_id = "-100123456789"
    cfg.thread_id = 42
    cfg.throttle_interval = 1.5
    cfg.save()

    loaded = Config.load()
    assert loaded.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert loaded.chat_id == "-100123456789"
    assert loaded.thread_id == 42
    assert loaded.throttle_interval == 1.5


def test_progress_helpers():
    assert format_size(0) == "0 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024 * 5) == "5.0 MB"

    assert format_time(65) == "01:05"
    assert format_time(3665) == "01:01:05"

    assert render_bar(50, 100, length=10) == "=====-----"
    assert render_bar(100, 100, length=10) == "=========="
    assert render_bar(0, 100, length=10) == "----------"


def test_telegram_client_mock():
    mock_client = TelegramClient(bot_token="test_token", chat_id="12345")

    with patch("curl_cffi.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "ok": True,
            "result": {"id": 999, "username": "test_bot", "first_name": "Test Bot"},
        }
        info = mock_client.get_me()
        assert info["username"] == "test_bot"

    with patch("curl_cffi.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 42, "text": "hello"},
        }
        res = mock_client.send_message("hello")
        assert res["message_id"] == 42

        # Test edit message
        mock_post.return_value.json.return_value = {"ok": True, "result": True}
        assert mock_client.edit_message(42, "updated") is True

        # Test message not modified
        mock_post.return_value.json.return_value = {
            "ok": False,
            "description": "Bad Request: message is not modified",
        }
        assert mock_client.edit_message(42, "same") is True


def test_reporter_throttling():
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.config = Config(throttle_interval=2.0)
    mock_client.send_message.return_value = {"message_id": 101}
    mock_client.edit_message.return_value = True

    reporter = TelegramProgressReporter(
        title="Test Download",
        client=mock_client,
        chat_id="12345",
        throttle_interval=2.0,
    )

    # Initial advance should trigger send_message
    reporter.advance(100, 1000)
    assert mock_client.send_message.call_count == 1
    assert mock_client.edit_message.call_count == 0

    # Immediate next advance within throttle_interval should be ignored
    reporter.advance(100, 1000)
    assert mock_client.edit_message.call_count == 0

    # Advance after throttle interval should edit
    reporter.last_edit_time = time.monotonic() - 3.0
    reporter.advance(200, 1000)
    assert mock_client.edit_message.call_count == 1

    # Finish should immediately flush edit
    reporter.finish(success_url="https://example.com/file.zip")
    assert mock_client.edit_message.call_count == 2
    assert reporter.finished is True


def test_create_reporter_skips_when_no_creds(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr("telegram.config.CONFIG_FILE", tmp_path / "absent.toml")
    rep = create_reporter("Test Title")
    assert rep is None


def test_telegram_cli_runner():
    runner = CliRunner()
    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    assert "Telegram notifications" in res.output

    res = runner.invoke(cli, ["config", "show"])
    assert res.exit_code == 0
    assert "Telegram Configuration" in res.output
