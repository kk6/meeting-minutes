"""daemon API のリクエスト・レスポンス型定義。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SessionState = Literal["idle", "running", "stopping", "failed"]


class StartRequest(BaseModel):
    """POST /sessions/start のリクエストボディ。全フィールドはオプション。"""

    model_config = ConfigDict(extra="forbid")

    overrides: dict[str, Any] | None = None
    draft_interval_minutes: int = Field(default=0, ge=0)


class SessionStatus(BaseModel):
    """セッションの現在状態。/sessions/current と /sessions/start のレスポンス。"""

    id: str
    state: SessionState
    started_at: datetime | None = None
    elapsed_seconds: int = 0
    session_dir: str | None = None
    transcript_path: str | None = None
    errors: list[str] = []
