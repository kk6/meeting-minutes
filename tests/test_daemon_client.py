"""daemon CLI client のテスト。"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from meeting_minutes.cli import app
from meeting_minutes.daemon.client import DaemonClient
from meeting_minutes.daemon.schema import SessionStatus, StartRequest


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


# ---------------------------------------------------------------------------
# DaemonClient 本体のテスト（httpx transport を差し替えて HTTP 層まで検証する）
# ---------------------------------------------------------------------------


class _FixedJsonTransport(httpx.BaseTransport):
    """固定 JSON レスポンスを返すテスト用 transport。最後のリクエストを記録する。"""

    def __init__(self, status_code: int, body: dict[str, object]) -> None:
        self._status_code = status_code
        self._body = body
        self.last_request: httpx.Request | None = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.last_request = request
        return httpx.Response(self._status_code, json=self._body, request=request)


def _patched_client(transport: httpx.BaseTransport) -> httpx.Client:
    return httpx.Client(base_url="http://127.0.0.1:8765", transport=transport)


_RUNNING_JSON = {
    "id": "20240101_120000",
    "state": "running",
    "started_at": "2024-01-01T12:00:00",
    "elapsed_seconds": 0,
    "errors": [],
}
_STOPPING_JSON = {"id": "20240101_120000", "state": "stopping", "elapsed_seconds": 0, "errors": []}
_CURRENT_JSON = {"id": "20240101_120000", "state": "idle", "elapsed_seconds": 0, "errors": []}


class TestDaemonClient:
    def test_start_posts_to_sessions_start(self) -> None:
        transport = _FixedJsonTransport(201, _RUNNING_JSON)
        with patch.object(DaemonClient, "_client", lambda self: _patched_client(transport)):
            result = DaemonClient().start(StartRequest())

        assert transport.last_request is not None
        assert transport.last_request.method == "POST"
        assert transport.last_request.url.path == "/sessions/start"
        assert isinstance(result, SessionStatus)
        assert result.state == "running"

    def test_stop_posts_to_sessions_stop(self) -> None:
        transport = _FixedJsonTransport(200, _STOPPING_JSON)
        with patch.object(DaemonClient, "_client", lambda self: _patched_client(transport)):
            result = DaemonClient().stop()

        assert transport.last_request is not None
        assert transport.last_request.method == "POST"
        assert transport.last_request.url.path == "/sessions/stop"
        assert result.state == "stopping"

    def test_current_gets_sessions_current(self) -> None:
        transport = _FixedJsonTransport(200, _CURRENT_JSON)
        with patch.object(DaemonClient, "_client", lambda self: _patched_client(transport)):
            result = DaemonClient().current()

        assert transport.last_request is not None
        assert transport.last_request.method == "GET"
        assert transport.last_request.url.path == "/sessions/current"
        assert result.state == "idle"

    def test_start_raises_http_status_error_on_non_2xx(self) -> None:
        transport = _FixedJsonTransport(409, {"detail": "session already running"})
        with (
            patch.object(DaemonClient, "_client", lambda self: _patched_client(transport)),
            pytest.raises(httpx.HTTPStatusError),
        ):
            DaemonClient().start(StartRequest())

    def test_start_sends_draft_interval_in_body(self) -> None:
        transport = _FixedJsonTransport(201, _RUNNING_JSON)
        with patch.object(DaemonClient, "_client", lambda self: _patched_client(transport)):
            DaemonClient().start(StartRequest(draft_interval_minutes=5))

        import json

        assert transport.last_request is not None
        body = json.loads(transport.last_request.content)
        assert body["draft_interval_minutes"] == 5


# ---------------------------------------------------------------------------
# CLI コマンドのテスト（_make_daemon_client をモックして CLI 層を検証する）
# ---------------------------------------------------------------------------


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

    def test_rejects_negative_draft_interval(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["start", "--draft-interval-minutes", "-1"])

        assert result.exit_code != 0


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
        assert "daemon" in result.output


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
        assert "daemon" in result.output
