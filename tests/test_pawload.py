from __future__ import annotations

from click.testing import CliRunner

from pawload.cli import cli


def test_pawload_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Pawload: Unified multi-cloud transfer" in result.output
    assert "gofile" in result.output
    assert "pixeldrain" in result.output
    assert "sourceforge" in result.output
    assert "vikingfile" in result.output
    assert "telegram" in result.output
    assert "web" in result.output


def test_pawload_subcommands_and_aliases():
    runner = CliRunner()

    # gofile full name and alias
    res_gf = runner.invoke(cli, ["gofile", "--help"])
    assert res_gf.exit_code == 0
    assert "GoFile CLI" in res_gf.output

    res_gf_alias = runner.invoke(cli, ["gf", "--help"])
    assert res_gf_alias.exit_code == 0
    assert "GoFile CLI" in res_gf_alias.output

    # pixeldrain alias
    res_pd = runner.invoke(cli, ["pd", "--help"])
    assert res_pd.exit_code == 0
    assert "Pixeldrain CLI" in res_pd.output

    # sourceforge alias
    res_sf = runner.invoke(cli, ["sf", "--help"])
    assert res_sf.exit_code == 0
    assert "SourceForge CLI" in res_sf.output

    # vikingfile alias
    res_vf = runner.invoke(cli, ["vf", "--help"])
    assert res_vf.exit_code == 0
    assert "VikingFile CLI" in res_vf.output

    # telegram alias
    res_tg = runner.invoke(cli, ["tg", "--help"])
    assert res_tg.exit_code == 0
    assert "Telegram notifications" in res_tg.output


def test_pawload_config_path(tmp_path, monkeypatch):
    import sourceforge.config as sf_cfg

    cfg_file = tmp_path / "custom_config.toml"
    monkeypatch.setattr(sf_cfg, "CONFIG_FILE", cfg_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "path"])
    assert result.exit_code == 0
    assert str(cfg_file) in result.output
