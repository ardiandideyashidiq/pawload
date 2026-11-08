from __future__ import annotations

from click.testing import CliRunner

import gofile.config as gf_cfg
import pixeldrain.config as pd_cfg
import sourceforge.config as sf_cfg
import telegram.config as tg_cfg
import vikingfile.config as vf_cfg
from sourceforge.cli import cli as sf_cli


def test_unified_config_cross_service(tmp_path, monkeypatch):
    unified_file = tmp_path / "config.toml"

    # Point all configs to the same file
    monkeypatch.setattr(sf_cfg, "CONFIG_FILE", unified_file)
    monkeypatch.setattr(gf_cfg, "CONFIG_FILE", unified_file)
    monkeypatch.setattr(vf_cfg, "CONFIG_FILE", unified_file)
    monkeypatch.setattr(pd_cfg, "CONFIG_FILE", unified_file)
    monkeypatch.setattr(tg_cfg, "CONFIG_FILE", unified_file)

    # 1. Populate initial config with multiple sections
    initial_content = """
[global]
concurrency = 6

[sourceforge]
project = "my-sf-project"
username = "sf-dev"

[gofile]
token = "gofile-secret-token"

[vikingfile]
user = "viking-user-hash"

[pixeldrain]
api_key = "pixeldrain-api-key"

[telegram]
bot_token = "123456:bot-token"
chat_id = "-100123"
"""
    unified_file.write_text(initial_content.strip(), encoding="utf-8")

    # 2. Check loading across all 5 clients
    sf = sf_cfg.Config.load()
    assert sf.project == "my-sf-project"
    assert sf.username == "sf-dev"
    assert sf.concurrency == 6  # Inherited from [global]

    gf = gf_cfg.Config.load()
    assert gf.token == "gofile-secret-token"
    assert gf.concurrency == 6  # Inherited from [global]

    vf = vf_cfg.Config.load()
    assert vf.user == "viking-user-hash"
    assert vf.concurrency == 6

    pd = pd_cfg.Config.load()
    assert pd.api_key == "pixeldrain-api-key"
    assert pd.concurrency == 6

    tg = tg_cfg.Config.load()
    assert tg.bot_token == "123456:bot-token"
    assert tg.chat_id == "-100123"

    # 3. Modify only pixeldrain and save
    pd.api_key = "updated-pd-key"
    pd.concurrency = 8
    pd.save()

    # 4. Verify other sections remain untouched in the file
    reloaded_sf = sf_cfg.Config.load()
    assert reloaded_sf.project == "my-sf-project"
    assert reloaded_sf.username == "sf-dev"

    reloaded_gf = gf_cfg.Config.load()
    assert reloaded_gf.token == "gofile-secret-token"

    reloaded_pd = pd_cfg.Config.load()
    assert reloaded_pd.api_key == "updated-pd-key"
    assert reloaded_pd.concurrency == 8

    reloaded_tg = tg_cfg.Config.load()
    assert reloaded_tg.bot_token == "123456:bot-token"


def test_cli_config_show_all_and_path(tmp_path, monkeypatch):
    unified_file = tmp_path / "config.toml"
    monkeypatch.setattr(sf_cfg, "CONFIG_FILE", unified_file)

    unified_file.write_text(
        """
[sourceforge]
project = "sample-proj"
username = "sample-user"

[pixeldrain]
api_key = "test-key"
""".strip(),
        encoding="utf-8",
    )

    runner = CliRunner()
    res = runner.invoke(sf_cli, ["config", "path"])
    assert res.exit_code == 0
    assert str(unified_file) in res.output

    res = runner.invoke(sf_cli, ["config", "show", "--all"])
    assert res.exit_code == 0
    assert "sourceforge" in res.output
    assert "pixeldrain" in res.output
    assert "sample-proj" in res.output
    assert "test-key" in res.output


def test_normalize_and_get_global_proxy(tmp_path, monkeypatch):
    from sourceforge.config import get_global_proxy, normalize_proxy

    assert normalize_proxy("127.0.0.1:1080") == "http://127.0.0.1:1080"
    assert normalize_proxy("socks5h://127.0.0.1:1080") == "socks5h://127.0.0.1:1080"
    assert normalize_proxy("") is None
    assert normalize_proxy(None) is None

    cfg_file = tmp_path / "proxy_test.toml"
    cfg_file.write_text("[global]\nproxy = 'socks5h://127.0.0.1:1080'\n")

    # Clean env for test
    monkeypatch.delenv("PAWLOAD_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    # 1. From config
    p = get_global_proxy(config_file=cfg_file)
    assert p == "socks5h://127.0.0.1:1080"

    # 2. Explicit flag overrides config
    p_override = get_global_proxy(explicit_proxy="http://10.0.0.1:8080", config_file=cfg_file)
    assert p_override == "http://10.0.0.1:8080"
