"""daemon FastAPI エンドポイントのテスト。"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from meeting_minutes.config import AppConfig
from meeting_minutes.daemon.schema import SessionStatus
from meeting_minutes.daemon.server import app
from meeting_minutes.daemon.session import SessionConflictError


def _idle_status(session_id: str = "20240101_120000") -> SessionStatus:
    return SessionStatus(id=session_id, state="idle")


def _running_status(session_id: str = "20240101_120000") -> SessionStatus:
    return SessionStatus(
        id=session_id,
        state="running",
        started_at=datetime(2024, 1, 1, 12, 0, 0),
        elapsed_seconds=0,
    )


def _stopping_status(session_id: str = "20240101_120000") -> SessionStatus:
    return SessionStatus(id=session_id, state="stopping")


@pytest.fixture
def fake_session(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("meeting_minutes.daemon.server._session", mock)
    monkeypatch.setattr("meeting_minutes.daemon.server._config", AppConfig())
    return mock


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestCsrfOriginCheck:
    def test_returns_403_when_origin_is_external_on_start(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        response = client.post(
            "/sessions/start", json={}, headers={"Origin": "https://evil.example.com"}
        )
        assert response.status_code == 403

    def test_returns_403_when_origin_is_external_on_stop(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        response = client.post("/sessions/stop", headers={"Origin": "https://evil.example.com"})
        assert response.status_code == 403

    def test_allows_localhost_origin_on_start(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.start.return_value = _running_status()

        response = client.post(
            "/sessions/start", json={}, headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 201

    def test_allows_request_without_origin_header_on_start(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        """Origin ヘッダーなし（curl 等）は CSRF リスクがないため許可する。"""
        fake_session.start.return_value = _running_status()

        response = client.post("/sessions/start", json={})
        assert response.status_code == 201


class TestStartSession:
    def test_returns_201_with_running_state_when_idle(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.start.return_value = _running_status()

        response = client.post("/sessions/start", json={})

        assert response.status_code == 201
        assert response.json()["state"] == "running"
        fake_session.start.assert_called_once()

    def test_returns_409_when_already_running(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.start.side_effect = SessionConflictError("session already running")

        response = client.post("/sessions/start", json={})

        assert response.status_code == 409
        assert "already running" in response.json()["detail"]

    def test_passes_overrides_and_draft_interval_to_session(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.start.return_value = _running_status()
        body = {
            "overrides": {"audio.chunk_seconds": 4},
            "draft_interval_minutes": 5,
        }

        client.post("/sessions/start", json=body)

        _, kwargs = fake_session.start.call_args
        assert kwargs["overrides"] == {"audio.chunk_seconds": 4}
        assert kwargs["draft_interval_minutes"] == 5

    def test_returns_422_when_override_raises_value_error(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.start.side_effect = ValueError("unknown section: bad.key")

        response = client.post("/sessions/start", json={"overrides": {"bad.key": 1}})

        assert response.status_code == 422

    def test_returns_422_for_unknown_top_level_field(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        response = client.post("/sessions/start", json={"unknownField": "value"})

        assert response.status_code == 422


class TestStopSession:
    def test_returns_200_with_stopping_state_when_running(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.stop.return_value = _stopping_status()

        response = client.post("/sessions/stop")

        assert response.status_code == 200
        assert response.json()["state"] == "stopping"

    def test_returns_409_when_no_session_running(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.stop.side_effect = SessionConflictError("no session is running")

        response = client.post("/sessions/stop")

        assert response.status_code == 409
        assert "no session" in response.json()["detail"]


class TestGetCurrentSession:
    def test_returns_idle_state_when_no_session(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.snapshot.return_value = _idle_status()

        response = client.get("/sessions/current")

        assert response.status_code == 200
        assert response.json()["state"] == "idle"

    def test_returns_running_state_during_session(
        self, client: TestClient, fake_session: MagicMock
    ) -> None:
        fake_session.snapshot.return_value = _running_status()

        response = client.get("/sessions/current")

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "running"
        assert data["started_at"] is not None
