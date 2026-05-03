"""daemon HTTP API の httpx クライアント。"""

import httpx

from meeting_minutes.daemon.schema import SessionStatus, StartRequest

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
# /sessions/start はモデルロード等で応答が遅れるため read を 300 秒に設定。
# stop / current は即応が期待できるため 10 秒で打ち切る。
_START_TIMEOUT = httpx.Timeout(connect=3.0, read=300.0, write=None, pool=None)
_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=None)


class DaemonClient:
    """daemon HTTP API を操作するクライアント。"""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def _client(self) -> httpx.Client:
        # trust_env=False でシステムの HTTP_PROXY 設定をバイパスする
        return httpx.Client(base_url=self._base_url, trust_env=False)

    def start(self, req: StartRequest) -> SessionStatus:
        """録音セッションを開始する。"""
        with self._client() as c:
            resp = c.post(
                "/sessions/start",
                json=req.model_dump(mode="json"),
                timeout=_START_TIMEOUT,
            )
            resp.raise_for_status()
            return SessionStatus.model_validate(resp.json())

    def stop(self) -> SessionStatus:
        """実行中のセッションを停止する。"""
        with self._client() as c:
            resp = c.post("/sessions/stop", timeout=_TIMEOUT)
            resp.raise_for_status()
            return SessionStatus.model_validate(resp.json())

    def current(self) -> SessionStatus:
        """現在のセッション状態を返す。"""
        with self._client() as c:
            resp = c.get("/sessions/current", timeout=_TIMEOUT)
            resp.raise_for_status()
            return SessionStatus.model_validate(resp.json())
