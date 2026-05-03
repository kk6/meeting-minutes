"""LiveSession スレッド動作の統合テスト。"""

import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from meeting_minutes.config import AppConfig
from meeting_minutes.daemon.session import LiveSession


@pytest.fixture
def config() -> AppConfig:
    return AppConfig()


class TestLiveSessionStateTransitions:
    def test_state_returns_to_idle_on_normal_completion(self, config: AppConfig) -> None:
        session = LiveSession()

        with patch("meeting_minutes.daemon.session.run_live"):
            session.start(config)
            assert session._thread is not None
            session._thread.join(timeout=5)

        assert session.snapshot().state == "idle"

    def test_state_becomes_failed_when_run_live_raises(self, config: AppConfig) -> None:
        session = LiveSession()

        with patch(
            "meeting_minutes.daemon.session.run_live",
            side_effect=RuntimeError("boom"),
        ):
            session.start(config)
            assert session._thread is not None
            session._thread.join(timeout=5)

        status = session.snapshot()
        assert status.state == "failed"
        assert len(status.errors) == 1
        assert "RuntimeError" in status.errors[0]
        assert "boom" in status.errors[0]

    def test_stop_sets_stopping_state_then_returns_to_idle(self, config: AppConfig) -> None:
        session = LiveSession()
        thread_started = threading.Event()

        def fake_run_live(
            cfg: Any, *, stop_event: Any = None, on_session_ready: Any = None, **kwargs: Any
        ) -> None:
            thread_started.set()
            if stop_event is not None:
                stop_event.wait(timeout=5)

        with patch("meeting_minutes.daemon.session.run_live", side_effect=fake_run_live):
            session.start(config)
            thread_started.wait(timeout=5)

            status = session.stop()
            assert status.state == "stopping"

            assert session._thread is not None
            session._thread.join(timeout=5)

        assert session.snapshot().state == "idle"


class TestLiveSessionCallback:
    def test_session_dir_and_transcript_path_set_via_callback(
        self, config: AppConfig, tmp_path: Path
    ) -> None:
        """on_session_ready コールバック経由でパスが LiveSession に伝播すること。"""
        session = LiveSession()
        expected_dir = str(tmp_path / "session")
        expected_transcript = str(tmp_path / "session" / "transcript.md")

        def fake_run_live(
            cfg: Any, *, stop_event: Any = None, on_session_ready: Any = None, **kwargs: Any
        ) -> None:
            if on_session_ready is not None:
                on_session_ready(expected_dir, expected_transcript)

        with patch("meeting_minutes.daemon.session.run_live", side_effect=fake_run_live):
            session.start(config)
            assert session._thread is not None
            session._thread.join(timeout=5)

        status = session.snapshot()
        assert status.session_dir == expected_dir
        assert status.transcript_path == expected_transcript

    def test_session_dir_is_none_when_callback_not_called(self, config: AppConfig) -> None:
        session = LiveSession()

        with patch("meeting_minutes.daemon.session.run_live"):
            session.start(config)
            assert session._thread is not None
            session._thread.join(timeout=5)

        status = session.snapshot()
        assert status.session_dir is None
        assert status.transcript_path is None
