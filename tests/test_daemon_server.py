"""daemon FastAPI エンドポイントのテスト。"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from meeting_minutes.daemon.schema import SessionStatus
from meeting_minutes.daemon.server import app


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
    return mock


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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
        fake_session.start.side_effect = RuntimeError("session already running")

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
        fake_session.stop.side_effect = RuntimeError("no session is running")

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
