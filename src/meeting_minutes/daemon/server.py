"""daemon の FastAPI アプリと 3 エンドポイント定義。"""

from fastapi import FastAPI, HTTPException

from meeting_minutes.config import AppConfig
from meeting_minutes.daemon.schema import SessionStatus, StartRequest
from meeting_minutes.daemon.session import LiveSession

app = FastAPI(title="meeting-minutes daemon", version="1.0")
_session = LiveSession()
_config: AppConfig = AppConfig()


def configure(config: AppConfig) -> None:
    """daemon 起動時に呼び出し、ベース設定を注入する。"""
    global _config
    _config = config


@app.post("/sessions/start", response_model=SessionStatus, status_code=201)  # type: ignore[misc]
def start_session(req: StartRequest) -> SessionStatus:
    """録音セッションを開始する。既に実行中の場合は 409 を返す。"""
    try:
        return _session.start(
            _config,
            overrides=req.overrides,
            draft_interval_minutes=req.draft_interval_minutes,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/sessions/stop", response_model=SessionStatus)  # type: ignore[misc]
def stop_session() -> SessionStatus:
    """実行中のセッションを停止する。セッションがなければ 409 を返す。"""
    try:
        return _session.stop()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/sessions/current", response_model=SessionStatus)  # type: ignore[misc]
def get_current_session() -> SessionStatus:
    """現在のセッション状態を返す。"""
    return _session.snapshot()
