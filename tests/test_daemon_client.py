"""daemon CLI client のテスト。"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from meeting_minutes.cli import app
from meeting_minutes.daemon.schema import SessionStatus


def _running_status() -> SessionStatus:
    return SessionStatus(
        id="20240101_120000",
        state="running",
        started_at=datetime(2024, 1, 1, 12, 0, 0),
        elapsed_seconds=30,
    )


def _idle_status() -> SessionStatus:
    return SessionStatus(id="20240101_120000", state="idle")


def _stopping_status() -> SessionStatus:
    return SessionStatus(id="20240101_120000", state="stopping")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestStartCommand:
    def test_prints_running_state_on_success(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.start.return_value = _running_status()
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["start"])

        assert result.exit_code == 0
        assert "running" in result.output

    def test_exits_with_error_when_daemon_not_running(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.start.side_effect = httpx.ConnectError("connection refused")
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["start"])

        assert result.exit_code == 1
        assert "daemon" in result.output

    def test_exits_with_error_on_409(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        http_err = httpx.HTTPStatusError(
            "409",
            request=MagicMock(),
            response=MagicMock(json=lambda: {"detail": "session already running"}),
        )
        mock_client.start.side_effect = http_err
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["start"])

        assert result.exit_code == 1
        assert "already running" in result.output


class TestStopCommand:
    def test_prints_stopping_state_on_success(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.stop.return_value = _stopping_status()
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        assert "stopping" in result.output

    def test_exits_with_error_when_daemon_not_running(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.stop.side_effect = httpx.ConnectError("connection refused")
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1


class TestStatusCommand:
    def test_prints_idle_state_when_no_session(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.current.return_value = _idle_status()
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "idle" in result.output

    def test_prints_running_state_with_elapsed(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.current.return_value = _running_status()
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "running" in result.output
        assert "30s" in result.output

    def test_exits_with_error_when_daemon_not_running(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.current.side_effect = httpx.ConnectError("connection refused")
        with patch("meeting_minutes.cli._make_daemon_client", return_value=mock_client):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
