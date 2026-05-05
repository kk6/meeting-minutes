"""`meeting-minutes config` サブコマンド群のテスト。"""

import json
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from meeting_minutes.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestConfigPath:
    def test_shows_explicit_when_config_option_given(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        explicit = tmp_path / "explicit.toml"
        result = runner.invoke(app, ["config", "path", "--config", str(explicit)])
        assert result.exit_code == 0
        assert "source: explicit" in result.stdout
        assert str(explicit) in result.stdout

    def test_shows_auto_discovered_when_xdg_config_exists(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").touch()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        result = runner.invoke(app, ["config", "path"])

        assert result.exit_code == 0
        assert "source: auto_discovered" in result.stdout

    def test_shows_defaults_when_no_config_found(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))

        result = runner.invoke(app, ["config", "path"])

        assert result.exit_code == 0
        assert "source: defaults" in result.stdout
        assert "would-be path:" in result.stdout


class TestConfigInit:
    def test_creates_template_at_xdg_default_path(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        result = runner.invoke(app, ["config", "init"])

        assert result.exit_code == 0
        target = tmp_path / "config" / "meeting-minutes" / "config.toml"
        assert target.exists()
        # 書き出した内容は TOML として妥当
        tomllib.loads(target.read_text(encoding="utf-8"))

    def test_refuses_to_overwrite_without_force(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        target = config_dir / "config.toml"
        target.write_text("# existing content\n", encoding="utf-8")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        result = runner.invoke(app, ["config", "init"])

        assert result.exit_code == 1
        # 既存ファイルは保持される
        assert target.read_text(encoding="utf-8") == "# existing content\n"

    def test_overwrites_when_force_specified(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        target = config_dir / "config.toml"
        target.write_text("# existing\n", encoding="utf-8")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        result = runner.invoke(app, ["config", "init", "--force"])

        assert result.exit_code == 0
        assert target.read_text(encoding="utf-8") != "# existing\n"


class TestConfigShow:
    def test_outputs_json_with_resolved_appconfig(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "show", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # 解決後の AppConfig セクションが含まれる
        assert "audio" in data
        assert "output" in data

    def test_json_preserves_null_for_unset_fields(self, runner: CliRunner) -> None:
        """JSON は null を表現できるので、未設定フィールド (audio.device など) を残す。

        TOML 出力が exclude_none=True なのは TOML 側の制約であって、JSON にまで
        その挙動を引きずらないことを担保する。
        """
        result = runner.invoke(app, ["config", "show", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # 既定で None のフィールドが null として保持されている
        assert data["audio"]["device"] is None
        assert data["audio"]["device_index"] is None
        assert data["vocabulary"]["glossary_file"] is None

    def test_outputs_toml_with_section_headers(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "show", "--format", "toml"])
        assert result.exit_code == 0
        assert "[audio]" in result.stdout
        # 出力は TOML として再パース可能
        tomllib.loads(result.stdout)

    def test_toml_drops_null_fields(self, runner: CliRunner) -> None:
        """TOML は null を表現できないため、None フィールドは出力から落とす必要がある。"""
        result = runner.invoke(app, ["config", "show", "--format", "toml"])
        assert result.exit_code == 0
        parsed = tomllib.loads(result.stdout)
        assert "device" not in parsed["audio"]
        assert "glossary_file" not in parsed["vocabulary"]

    def test_rejects_unknown_format(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "show", "--format", "yaml"])
        assert result.exit_code != 0


class TestConfigEdit:
    def test_invokes_editor_on_resolved_config_path(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        target = config_dir / "config.toml"
        target.touch()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("EDITOR", "fake-editor")

        with patch("meeting_minutes.config.cli.subprocess.run") as run_mock:
            result = runner.invoke(app, ["config", "edit"])

        assert result.exit_code == 0
        run_mock.assert_called_once_with(["fake-editor", str(target)], check=True)

    def test_errors_when_no_config_file_exists(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))

        result = runner.invoke(app, ["config", "edit"])

        assert result.exit_code == 1
        assert "config init" in result.stdout

    def test_falls_back_to_open_when_editor_unset(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        target = config_dir / "config.toml"
        target.touch()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.delenv("EDITOR", raising=False)

        with (
            patch("meeting_minutes.config.cli.shutil.which", return_value="/usr/bin/open"),
            patch("meeting_minutes.config.cli.subprocess.run") as run_mock,
        ):
            result = runner.invoke(app, ["config", "edit"])

        assert result.exit_code == 0
        run_mock.assert_called_once_with(["/usr/bin/open", str(target)], check=True)

    def test_errors_when_editor_unset_and_open_missing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").touch()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.delenv("EDITOR", raising=False)

        with patch("meeting_minutes.config.cli.shutil.which", return_value=None):
            result = runner.invoke(app, ["config", "edit"])

        assert result.exit_code == 1
        assert "open(1)" in result.stdout

    def test_opens_explicit_config_when_path_option_given(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        explicit = tmp_path / "alt.toml"
        explicit.touch()
        # XDG 側に config が無くても --config 経由で開けることを確認する。
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))
        monkeypatch.setenv("EDITOR", "fake-editor")

        with patch("meeting_minutes.config.cli.subprocess.run") as run_mock:
            result = runner.invoke(app, ["config", "edit", "--config", str(explicit)])

        assert result.exit_code == 0
        run_mock.assert_called_once_with(["fake-editor", str(explicit)], check=True)

    def test_errors_when_explicit_config_missing(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(app, ["config", "edit", "--config", str(tmp_path / "missing.toml")])

        assert result.exit_code == 1
        assert "見つかりません" in result.stdout
