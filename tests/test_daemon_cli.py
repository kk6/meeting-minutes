"""`meeting-minutes daemon` CLI のテスト（serve 起動時の参照先ログ等）。"""

import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from meeting_minutes.cli import app
from meeting_minutes.config import OutputConfig
from meeting_minutes.daemon import cli as daemon_cli


@pytest.fixture(autouse=True)
def reset_daemon_logger() -> Iterator[None]:
    """`_ensure_daemon_logger` が `propagate=False` を立てるため、
    そのままだと caplog が記録を拾えない。各テストの前後でロガー状態を初期化する。

    （production では uvicorn のログ二重出力を避けるため `propagate=False` が正しい挙動なので、
    テスト側でのみ propagate を有効化する。）
    """
    logger = logging.getLogger(daemon_cli._DAEMON_LOGGER_NAME)
    original_handlers = logger.handlers[:]
    original_propagate = logger.propagate
    original_level = logger.level
    logger.handlers = []
    logger.propagate = True
    logger.setLevel(logging.NOTSET)
    yield
    logger.handlers = original_handlers
    logger.propagate = original_propagate
    logger.setLevel(original_level)


def _daemon_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """caplog から daemon ロガー由来のメッセージだけ抜き出す。

    pytest-randomly で他テスト由来の record が混じっても判定が壊れないようにする。
    """
    return [r.getMessage() for r in caplog.records if r.name == daemon_cli._DAEMON_LOGGER_NAME]


class TestLogDaemonStartup:
    def test_emits_config_and_output_lines_in_order(
        self, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ) -> None:
        logger = logging.getLogger(daemon_cli._DAEMON_LOGGER_NAME)
        with caplog.at_level(logging.INFO, logger=daemon_cli._DAEMON_LOGGER_NAME):
            daemon_cli._log_daemon_startup(
                logger,
                source_description="auto_discovered (/path/to/config.toml)",
                output_base_dir=tmp_path / "out",
            )

        assert _daemon_messages(caplog) == [
            "config source: auto_discovered (/path/to/config.toml)",
            f"output base_dir: {tmp_path / 'out'}",
        ]

    def test_does_not_emit_listening_line(
        self, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ) -> None:
        """uvicorn が `Uvicorn running on http://...` を自分で出すので、
        bind 前に重複/虚偽の listening 行を出さないことを担保する。"""
        logger = logging.getLogger(daemon_cli._DAEMON_LOGGER_NAME)
        with caplog.at_level(logging.INFO, logger=daemon_cli._DAEMON_LOGGER_NAME):
            daemon_cli._log_daemon_startup(
                logger,
                source_description="defaults",
                output_base_dir=tmp_path / "out",
            )

        # "listening on" / "127.0.0.1:" のいずれも daemon ロガー出力に含まれてはならない。
        # （tmp_path のテスト名にたまたま "listening" が含まれるケースを避けるため、
        # より具体的な部分文字列で判定する。）
        for msg in _daemon_messages(caplog):
            assert "listening on" not in msg
            assert "127.0.0.1:" not in msg


class TestEnsureDaemonLogger:
    def test_does_not_add_duplicate_handler_on_repeat_calls(self) -> None:
        first = daemon_cli._ensure_daemon_logger()
        # 初回呼び出しでハンドラが 1 つ付与され、2 回目以降は増えないことを確認する。
        after_first = len(first.handlers)
        assert after_first >= 1

        second = daemon_cli._ensure_daemon_logger()
        assert first is second
        assert len(second.handlers) == after_first


class TestDescribeConfigSourceFromCli:
    """daemon serve 用に `describe_config_source` がどの種別も識別できることを確認する。"""

    def test_describes_explicit_source(self, tmp_path: Path) -> None:
        from meeting_minutes.config import resolve_config_source
        from meeting_minutes.config.cli import describe_config_source

        explicit = tmp_path / "explicit.toml"
        description = describe_config_source(resolve_config_source(explicit))
        assert description.startswith("explicit (")
        assert str(explicit) in description

    def test_describes_auto_discovered_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from meeting_minutes.config import resolve_config_source
        from meeting_minutes.config.cli import describe_config_source

        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").touch()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        description = describe_config_source(resolve_config_source(None))
        assert description.startswith("auto_discovered (")

    def test_describes_defaults_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from meeting_minutes.config import resolve_config_source
        from meeting_minutes.config.cli import describe_config_source

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))

        description = describe_config_source(resolve_config_source(None))
        assert description.startswith("defaults (no config file at ")


def test_appconfig_output_base_dir_used_in_log(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """ログには `AppConfig.output.base_dir` の解決結果（XDG 既定 or TOML 上書き）が出る。"""
    output = OutputConfig(base_dir=tmp_path / "custom-out")
    logger = logging.getLogger(daemon_cli._DAEMON_LOGGER_NAME)

    with caplog.at_level(logging.INFO, logger=daemon_cli._DAEMON_LOGGER_NAME):
        daemon_cli._log_daemon_startup(
            logger,
            source_description="defaults",
            output_base_dir=output.base_dir,
        )

    assert f"output base_dir: {tmp_path / 'custom-out'}" in _daemon_messages(caplog)


class TestDaemonServeCommand:
    """`daemon serve` の起動経路を結合的に検証する。

    `_log_daemon_startup` 単体テストだけでは「ログ呼び出しが消える」「uvicorn より
    後にログを出してしまう」といった配線ミスを拾えないため、CLI 経由で uvicorn を
    モックして起動順序と引数を検証する。
    """

    def test_logs_config_and_output_then_calls_uvicorn(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        config_dir = tmp_path / "config" / "meeting-minutes"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").touch()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

        # uvicorn.run の呼び出し時点で stderr にマーカーを書き込み、その前後で
        # daemon ログの出現位置を比較することで「ログ → uvicorn.run」の順序を
        # 厳密に保証する（呼び出しの有無だけ assert したのでは、実装が
        # uvicorn.run の後にログを出してもテストが通ってしまうため）。
        def fake_uvicorn_run(*_args: object, **_kwargs: object) -> None:
            sys.stderr.write("__UVICORN_RUN_CALLED__\n")

        # 起動ログは StreamHandler 経由で stderr に出る（_ensure_daemon_logger が
        # propagate=False を立てるため caplog では拾えない）。Click 8.3+ の CliRunner は
        # 既定で stderr を独立ストリームに退避するので result.stderr で取り出して検証する。
        runner = CliRunner()
        with patch("uvicorn.run", side_effect=fake_uvicorn_run) as uvicorn_run:
            result = runner.invoke(app, ["daemon", "serve", "--port", "9001"])

        assert result.exit_code == 0, result.output
        # uvicorn.run が 127.0.0.1:9001 で呼ばれたか
        uvicorn_run.assert_called_once()
        kwargs = uvicorn_run.call_args.kwargs
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 9001
        # ログ 2 行が現れ、いずれもマーカー（uvicorn.run 呼び出し時点）より前にある
        stderr = result.stderr
        marker_pos = stderr.find("__UVICORN_RUN_CALLED__")
        config_pos = stderr.find("INFO: config source: auto_discovered (")
        output_pos = stderr.find("INFO: output base_dir: ")
        assert marker_pos != -1
        assert 0 <= config_pos < marker_pos
        assert 0 <= output_pos < marker_pos
        # listening 行は CLI からは出さない（uvicorn 自身に委譲）
        assert "listening on" not in stderr
