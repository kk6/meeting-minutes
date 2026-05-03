"""daemon の FastAPI アプリと 3 エンドポイント定義。"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from meeting_minutes.config import AppConfig
from meeting_minutes.daemon.schema import SessionStatus, StartRequest
from meeting_minutes.daemon.session import LiveSession, SessionConflictError

_session = LiveSession()
_config: AppConfig | None = None


def configure(config: AppConfig) -> None:
    """daemon 起動時に呼び出し、ベース設定を注入する。"""
    global _config
    _config = config


def _get_config() -> AppConfig:
    if _config is None:
        return AppConfig()
    return _config


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    _session.shutdown()


app = FastAPI(
    title="meeting-minutes daemon",
    version="1.0",
    lifespan=_lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.post("/sessions/start", response_model=SessionStatus, status_code=201)
def start_session(req: StartRequest | None = None) -> SessionStatus:
    """録音セッションを開始する。既に実行中の場合は 409 を返す。"""
    if req is None:
        req = StartRequest()
    try:
        return _session.start(
            _get_config(),
            overrides=req.overrides,
            draft_interval_minutes=req.draft_interval_minutes,
        )
    except SessionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/sessions/stop", response_model=SessionStatus)
def stop_session() -> SessionStatus:
    """実行中のセッションを停止する。セッションがなければ 409 を返す。"""
    try:
        return _session.stop()
    except SessionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/sessions/current", response_model=SessionStatus)
def get_current_session() -> SessionStatus:
    """現在のセッション状態を返す。"""
    return _session.snapshot()
