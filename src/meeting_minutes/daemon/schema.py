"""daemon API のリクエスト・レスポンス型定義。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class StartRequest(BaseModel):
    """POST /sessions/start のリクエストボディ。"""

    overrides: dict[str, Any] | None = None
    draft_interval_minutes: int = 0


class SessionStatus(BaseModel):
    """セッションの現在状態。/sessions/current と /sessions/start のレスポンス。"""

    id: str
    state: Literal["idle", "running", "stopping", "failed"]
    started_at: datetime | None = None
    elapsed_seconds: int = 0
    session_dir: str | None = None
    transcript_path: str | None = None
    errors: list[str] = []
