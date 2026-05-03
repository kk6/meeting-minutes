"""daemon HTTP API の httpx クライアント。"""

import httpx

from meeting_minutes.daemon.schema import SessionStatus, StartRequest

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
_CONNECT_TIMEOUT = 3.0


class DaemonClient:
    """daemon HTTP API を操作するクライアント。"""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base_url, timeout=_CONNECT_TIMEOUT)

    def start(self, req: StartRequest) -> SessionStatus:
        """録音セッションを開始する。"""
        with self._client() as c:
            resp = c.post("/sessions/start", json=req.model_dump())
            resp.raise_for_status()
            return SessionStatus.model_validate(resp.json())

    def stop(self) -> SessionStatus:
        """実行中のセッションを停止する。"""
        with self._client() as c:
            resp = c.post("/sessions/stop")
            resp.raise_for_status()
            return SessionStatus.model_validate(resp.json())

    def current(self) -> SessionStatus:
        """現在のセッション状態を返す。"""
        with self._client() as c:
            resp = c.get("/sessions/current")
            resp.raise_for_status()
            return SessionStatus.model_validate(resp.json())
