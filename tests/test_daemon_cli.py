"""`meeting-minutes daemon` CLI のテスト（serve 起動時の参照先ログ等）。"""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

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


class TestLogDaemonStartup:
    def test_emits_three_info_lines_in_order(
        self, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ) -> None:
        logger = logging.getLogger(daemon_cli._DAEMON_LOGGER_NAME)
        with caplog.at_level(logging.INFO, logger=daemon_cli._DAEMON_LOGGER_NAME):
            daemon_cli._log_daemon_startup(
                logger,
                source_description="auto_discovered (/path/to/config.toml)",
                output_base_dir=tmp_path / "out",
                port=8765,
            )

        messages = [r.getMessage() for r in caplog.records]
        assert messages == [
            "config source: auto_discovered (/path/to/config.toml)",
            f"output base_dir: {tmp_path / 'out'}",
            "listening on http://127.0.0.1:8765",
        ]


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
            port=9000,
        )

    assert any(
        f"output base_dir: {tmp_path / 'custom-out'}" == r.getMessage() for r in caplog.records
    )
