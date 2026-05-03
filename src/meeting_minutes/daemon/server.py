"""daemon の FastAPI アプリと 3 エンドポイント定義。"""

import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from meeting_minutes.config import AppConfig
from meeting_minutes.daemon.schema import SessionStatus, StartRequest
from meeting_minutes.daemon.session import LiveSession, SessionConflictError

_LOCALHOST_ORIGIN_RE = re.compile(r"https?://(localhost|127\.0\.0\.1)(:\d+)?$")

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


async def _require_local_origin(request: Request) -> None:
    """ブラウザからの CSRF を防ぐため、Origin ヘッダーが localhost 以外なら 403 を返す。"""
    origin = request.headers.get("origin")
    if origin is not None and not _LOCALHOST_ORIGIN_RE.match(origin):
        raise HTTPException(status_code=403, detail="cross-origin requests are not allowed")


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    _session.shutdown()


app = FastAPI(
    title="meeting-minutes daemon",
    version="1.0",
    lifespan=_lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=None,
)

# localhost 上の Web UI からの呼び出しを許可しつつ、外部オリジンからの CSRF を防ぐ。
# JSON POST はシンプルリクエストではないためプリフライトが必須となり、
# 許可されていないオリジンからの実際のリクエストはブラウザにブロックされる。
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.post(
    "/sessions/start",
    response_model=SessionStatus,
    status_code=201,
    dependencies=[Depends(_require_local_origin)],
)  # noqa: E501
def start_session(req: StartRequest | None = None) -> SessionStatus:
    """録音セッションを開始する。既に実行中の場合は 409 を返す。"""
    if req is None:
        req = StartRequest()
    try:
        status = _session.start(
            _get_config(),
            overrides=req.overrides,
            draft_interval_minutes=req.draft_interval_minutes,
        )
    except SessionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if status.state == "failed":
        detail = status.errors[0] if status.errors else "session startup failed"
        raise HTTPException(status_code=500, detail=detail)
    return status


@app.post(
    "/sessions/stop", response_model=SessionStatus, dependencies=[Depends(_require_local_origin)]
)
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
