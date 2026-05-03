"""ライブ録音セッションをスレッドで管理する LiveSession クラス。"""

import logging
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime

from meeting_minutes.config import AppConfig, apply_overrides
from meeting_minutes.daemon.schema import SessionState, SessionStatus
from meeting_minutes.transcription.live import run_live

logger = logging.getLogger(__name__)

# モデルロード待ちではなく、デバイス未検出などの同期的な起動失敗を
# キャッチするための短い窓。長いロード時間を待つ目的ではない。
_STARTUP_TIMEOUT = 2.0


class SessionConflictError(RuntimeError):
    """セッションの状態が操作と競合するときに送出する。"""


@dataclass
class LiveSession:
    """録音セッションを所有し、HTTP API 経由で start / stop / status を管理する。"""

    _state: SessionState = field(default="idle", init=False)
    _session_id: str = field(default="", init=False)
    _started_at: datetime | None = field(default=None, init=False)
    _elapsed_seconds: int = field(default=0, init=False)
    _session_dir: str | None = field(default=None, init=False)
    _transcript_path: str | None = field(default=None, init=False)
    _errors: list[str] = field(default_factory=list, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def start(
        self,
        base_config: AppConfig,
        *,
        overrides: dict[str, object] | None = None,
        draft_interval_minutes: int = 0,
    ) -> SessionStatus:
        """録音セッションを開始する。既に実行中なら SessionConflictError を送出する。"""
        with self._lock:
            if self._state in ("running", "stopping"):
                raise SessionConflictError("session already running")
            config = apply_overrides(base_config, overrides or {})
            self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self._started_at = datetime.now()
            self._elapsed_seconds = 0
            self._session_dir = None
            self._transcript_path = None
            self._errors = []
            self._stop_event.clear()
            self._state = "running"
            # セッションごとに新しい Event を生成することで、前セッションのスレッドが
            # 遅れて set() しても新セッションに影響しないようにする。
            startup_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run,
                args=(config, draft_interval_minutes, startup_event),
                daemon=True,
                name=f"live-session-{self._session_id}",
            )

        try:
            self._thread.start()
        except OSError:
            with self._lock:
                self._freeze_elapsed()
                self._state = "failed"
                self._errors.append(traceback.format_exc())
            raise

        # デバイス未検出・設定不正などの同期的な起動失敗を短時間待って反映させる。
        # タイムアウト後も state が running なら非同期的に起動中と見なし、そのまま返す。
        startup_event.wait(timeout=_STARTUP_TIMEOUT)
        return self._snapshot()

    def stop(self) -> SessionStatus:
        """実行中のセッションに停止を要求する。
        セッションがなければ SessionConflictError を送出する。
        """
        with self._lock:
            if self._state != "running":
                raise SessionConflictError("no session is running")
            self._state = "stopping"
            self._stop_event.set()
        return self._snapshot()

    def shutdown(self, *, timeout: float = 30.0) -> None:
        """プロセス終了時に呼び出し、実行中セッションの完了を待つ。"""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(
                    "live-session thread did not stop within %.0fs; "
                    "process will exit with it still running",
                    timeout,
                )

    def snapshot(self) -> SessionStatus:
        """現在のセッション状態を返す。"""
        return self._snapshot()

    def _snapshot(self) -> SessionStatus:
        with self._lock:
            if self._state in ("running", "stopping") and self._started_at is not None:
                elapsed = int((datetime.now() - self._started_at).total_seconds())
            else:
                elapsed = self._elapsed_seconds
            return SessionStatus(
                id=self._session_id,
                state=self._state,
                started_at=self._started_at,
                elapsed_seconds=elapsed,
                session_dir=self._session_dir,
                transcript_path=self._transcript_path,
                errors=list(self._errors),
            )

    def _on_session_dir_ready(
        self, session_dir: str, transcript_path: str | None, startup_event: threading.Event
    ) -> None:
        with self._lock:
            self._session_dir = session_dir
            self._transcript_path = transcript_path
        startup_event.set()

    def _freeze_elapsed(self) -> None:
        """セッション終了時に経過秒数を確定し、started_at をクリアする。"""
        if self._started_at is not None:
            self._elapsed_seconds = int((datetime.now() - self._started_at).total_seconds())
            self._started_at = None

    def _run(
        self, config: AppConfig, draft_interval_minutes: int, startup_event: threading.Event
    ) -> None:
        def on_ready(session_dir: str, transcript_path: str | None) -> None:
            self._on_session_dir_ready(session_dir, transcript_path, startup_event)

        try:
            run_live(
                config,
                draft_interval_minutes=draft_interval_minutes,
                stop_event=self._stop_event,
                on_session_ready=on_ready,
            )
        except Exception:
            logger.exception("Live session thread raised an exception")
            with self._lock:
                self._errors.append(traceback.format_exc())
                self._freeze_elapsed()
                self._state = "failed"
            startup_event.set()
            return
        with self._lock:
            if self._state != "failed":
                self._freeze_elapsed()
                self._state = "idle"
        # on_session_ready が呼ばれなかった場合のフォールバック（モック等）
        startup_event.set()
