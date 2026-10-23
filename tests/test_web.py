from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from sourceforge.cli import cli as sf_cli
from web.app import create_app
from web.bridge import WebBridge
from web.cli import cli as web_cli


@pytest.fixture
def temp_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("PAWLOAD_CONFIG", str(cfg))
    return cfg


def test_assets_exist() -> None:
    pkg_dir = Path(__file__).parent.parent / "src" / "web"
    dist_dir = pkg_dir / "dist"
    index_html = dist_dir / "index.html"

    assert index_html.is_file()
    content = index_html.read_text(encoding="utf-8")
    assert "Pawload" in content
    assert "dark" in content

    assets = list((dist_dir / "assets").glob("*.js"))
    assert len(assets) > 0


def test_bridge_config(temp_config_file: Path) -> None:
    bridge = WebBridge()
    info = bridge.get_active_config()
    assert info["path"] == str(temp_config_file)
    assert isinstance(info["config"], dict)

    success = bridge.save_config_section("gofile", {"token": "test-gf-token-123"})
    assert success is True

    updated = bridge.get_active_config()
    assert updated["config"]["gofile"]["token"] == "test-gf-token-123"


def test_bridge_inspect_local_file(tmp_path: Path) -> None:
    test_file = tmp_path / "sample_archive.zip"
    test_file.write_bytes(b"PK00" + b"\x00" * 1020)

    bridge = WebBridge()
    info = bridge.inspect_target(str(test_file))
    assert info["provider"] == "local"
    assert info["name"] == "sample_archive.zip"
    assert info["size"] == 1024


def test_bridge_inspect_sourceforge() -> None:
    bridge = WebBridge()
    info = bridge.inspect_target(
        "https://sourceforge.net/projects/lineageos/files/rom.zip/download"
    )
    assert info["provider"] == "sourceforge"
    assert info["project"] == "lineageos"
    assert info["name"] == "rom.zip"
    assert isinstance(info.get("mirrors"), list)


def test_bridge_transfer_lifecycle(tmp_path: Path) -> None:
    bridge = WebBridge()

    with (
        patch.object(
            bridge,
            "inspect_target",
            return_value={"provider": "sourceforge", "name": "rom.zip", "size": 1000},
        ),
        patch(
            "web.bridge.SourceForgeClient.download_async", new_callable=AsyncMock
        ) as mock_dl,
    ):
        mock_dl.return_value = tmp_path / "rom.zip"

        tid = bridge.start_download(
            target="https://sourceforge.net/projects/test/files/rom.zip/download",
            output_dir=str(tmp_path),
            concurrency=4,
            notify=False,
        )

        assert tid.startswith("dl_")
        transfers = bridge.get_transfers()
        assert len(transfers) >= 1
        rec = next(t for t in transfers if t["id"] == tid)
        assert rec["provider"] == "sourceforge"
        assert rec["name"] == "rom.zip"

        paused = bridge.pause_transfer(tid)
        assert paused in (True, False)

        cancelled = bridge.cancel_transfer(tid)
        assert cancelled is True
        assert rec["status"] == "cancelled"


def test_flask_routes(temp_config_file: Path, tmp_path: Path) -> None:
    bridge = WebBridge()
    app = create_app(bridge)
    client = app.test_client()

    # Index page
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Pawload" in resp.data

    # Config API
    resp = client.get("/api/config")
    assert resp.status_code == 200
    cfg = resp.get_json()
    assert "config" in cfg

    # Save Config
    resp = client.post(
        "/api/config", json={"section": "telegram", "data": {"chat_id": "12345"}}
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # Inspect API
    resp = client.post("/api/inspect", json={"target": "sf:lineageos/rom.zip"})
    assert resp.status_code == 200
    assert resp.get_json()["provider"] == "sourceforge"

    # Transfers list
    resp = client.get("/api/transfers")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)

    # Start download
    with (
        patch.object(
            bridge,
            "inspect_target",
            return_value={"provider": "sourceforge", "name": "rom.zip", "size": 500},
        ),
        patch(
            "web.bridge.SourceForgeClient.download_async", new_callable=AsyncMock
        ) as mock_dl,
    ):
        mock_dl.return_value = tmp_path / "rom.zip"
        dl_resp = client.post(
            "/api/download",
            json={"target": "sf:test/rom.zip", "output_dir": str(tmp_path)},
        )
        assert dl_resp.status_code == 200
        tid = dl_resp.get_json()["transfer_id"]

        # Pause and cancel
        p_resp = client.post(f"/api/transfers/{tid}/pause")
        assert p_resp.status_code == 200

        c_resp = client.post(f"/api/transfers/{tid}/cancel")
        assert c_resp.status_code == 200


def test_flask_sse_events() -> None:
    bridge = WebBridge()
    app = create_app(bridge)
    client = app.test_client()

    resp = client.get("/api/events")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("text/event-stream")

    gen = resp.response
    line1 = next(gen)
    assert b": connected" in line1
    line2 = next(gen)
    assert b"event: init" in line2

    # Test dispatching a transfer event
    bridge.dispatch_event("transfer_added", {"id": "test_1", "type": "upload", "status": "running"})
    line3 = next(gen)
    assert b"event: transfer_added" in line3
    assert b'"id": "test_1"' in line3

    bridge.dispatch_event("transfer_completed", {"id": "test_1", "type": "upload", "status": "completed"})
    line4 = next(gen)
    assert b"event: transfer_completed" in line4
    assert b'"status": "completed"' in line4

def test_cli_help() -> None:
    runner = CliRunner()
    res = runner.invoke(web_cli, ["--help"])
    assert res.exit_code == 0
    assert "Pawload Web App" in res.output

    res_serve = runner.invoke(web_cli, ["serve", "--help"])
    assert res_serve.exit_code == 0
    assert "--host" in res_serve.output

    res_sf = runner.invoke(sf_cli, ["web", "--help"])
    assert res_sf.exit_code == 0
    assert "Pawload Web Transfer Dashboard" in res_sf.output


def test_flask_fallback_when_dist_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_dir = tmp_path / "empty_web"
    empty_dir.mkdir()
    bridge = WebBridge()
    with patch("web.app.Path") as mock_path:
        mock_path.return_value.parent = empty_dir
        mock_path.__file__ = str(empty_dir / "app.py")
        app = create_app(bridge)
        client = app.test_client()
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Pawload Frontend Not Built" in resp.data


def test_flask_upload_file_multipart(tmp_path: Path) -> None:
    import io

    bridge = WebBridge()
    app = create_app(bridge)
    client = app.test_client()

    with patch.object(bridge, "start_upload", return_value="ul_test_123") as mock_up:
        data = {
            "file": (io.BytesIO(b"dummy payload"), "sample.txt"),
            "provider": "gofile",
            "folder_id": "test_folder",
        }
        resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert resp.get_json()["transfer_id"] == "ul_test_123"
        mock_up.assert_called_once()
        called_kwargs = mock_up.call_args[1]
        assert called_kwargs["provider"] == "gofile"
        assert called_kwargs["remote_path"] == "test_folder"
        assert "sample.txt" in called_kwargs["local_path"]


def test_flask_verbose_logging() -> None:
    bridge = WebBridge()
    app = create_app(bridge, verbose=2)
    client = app.test_client()

    resp = client.get("/api/transfers")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)
