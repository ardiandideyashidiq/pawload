from __future__ import annotations

import tempfile
from pathlib import Path

from sourceforge.cli import format_size
from sourceforge.client import SourceForgeClient, list_files_rss
from sourceforge.config import Config
from sourceforge.downloader import DownloadState, get_expected_md5
from sourceforge.mirrors import (
    fetch_live_mirrors,
    parse_target,
    resolve_download_target,
)


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(500) == "500 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024 * 5) == "5.0 MB"
    assert format_size(1024 * 1024 * 1024 * 2) == "2.0 GB"


def test_config_save_and_load(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg_file = tmp_path / "config.toml"
        monkeypatch.setattr("sourceforge.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("sourceforge.config.CONFIG_FILE", cfg_file)

        cfg = Config(
            username="testuser",
            project="testproj",
            key_path="/tmp/key",
            default_mirror="master",
            concurrency=8,
            chunk_size=4 * 1024 * 1024,
        )
        cfg.save()

        loaded = Config.load()
        assert loaded.username == "testuser"
        assert loaded.project == "testproj"
        assert loaded.key_path == "/tmp/key"
        assert loaded.default_mirror == "master"
        assert loaded.concurrency == 8
        assert loaded.chunk_size == 4 * 1024 * 1024


def test_download_state_sidecar():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "test.sfdownload"
        state = DownloadState(
            url="https://example.com/file.zip",
            total_bytes=1000,
            chunk_size=100,
            completed_chunks=[0, 1, 2],
        )
        state.save(state_file)

        loaded = DownloadState.load(state_file)
        assert loaded is not None
        assert loaded.url == "https://example.com/file.zip"
        assert loaded.total_bytes == 1000
        assert loaded.completed_chunks == [0, 1, 2]



def test_rss_feed_listing_live():
    items = list_files_rss(project="rdndds-release", remote_dir="rom")
    assert len(items) >= 2
    filenames = [i.name for i in items]
    assert "README.md" in filenames
    readme_item = next(i for i in items if i.name == "README.md")
    assert readme_item.md5 == "d028d317b579d2f6cba920b425f7f9f9"
    assert readme_item.size > 0


def test_get_expected_md5_live():
    md5 = get_expected_md5("rdndds-release", "rom/README.md")
    assert md5 == "d028d317b579d2f6cba920b425f7f9f9"


def test_resolve_download_target_live():
    target = resolve_download_target(
        project="rdndds-release",
        remote_path="rom/README.md",
        mirror="master",
        interactive_prompt=False,
    )
    assert target.content_length == 1119
    assert target.accept_ranges is True
    assert "master.dl.sourceforge.net" in target.direct_url


def test_client_download_and_verify():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = SourceForgeClient(project="rdndds-release")
        out_file = Path(tmpdir) / "README.md"
        dest = client.download(
            remote_path="rom/README.md",
            output_path=out_file,
            mirror="master",
            concurrency=2,
            verify_checksum=True,
            interactive_prompt=False,
        )
        assert dest.is_file()
        assert dest.stat().st_size == 1119
        assert "uploader" in dest.read_text(encoding="utf-8")


def test_parse_target_project_url():
    info = parse_target("https://sourceforge.net/projects/netmodhttp/")
    assert info.project == "netmodhttp"
    assert info.is_project_or_dir is True


def test_parse_target_file_url():
    info = parse_target("https://sourceforge.net/projects/rdndds-release/files/rom/README.md/download")
    assert info.project == "rdndds-release"
    assert info.remote_path == "rom/README.md"
    assert info.is_project_or_dir is False


def test_parse_target_bare_project():
    info = parse_target("netmodhttp")
    assert info.project == "netmodhttp"
    assert info.is_project_or_dir is True


def test_fetch_live_mirrors_live():
    mirrors = fetch_live_mirrors("netmodhttp", "Setup/NetMod_x86(Latest).exe")
    assert len(mirrors) >= 2
    ids = [m.id for m in mirrors]
    assert "autoselect" in ids
