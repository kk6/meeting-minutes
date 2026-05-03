"""録音セッションの実行メタデータ（環境・成果物パス・統計）の構築と保存。"""

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from meeting_minutes.audio.devices import InputDevice
from meeting_minutes.config import AppConfig


class SessionMetadata(BaseModel):
    """1 セッション分の収録条件・成果物・エラー履歴を保持するモデル。"""

    started_at: datetime
    ended_at: datetime | None = None
    input_device_name: str
    input_device_index: int
    sample_rate: int
    chunk_seconds: int
    whisper_model: str
    ollama_model: str
    language: str
    transcript_path: Path | None
    audio_path: Path | None
    transcript_rejections: dict[str, int | dict[str, int]]
    errors: list[str]
    processing_seconds: float | None = None


def build_metadata(
    *,
    started_at: datetime,
    ended_at: datetime | None,
    input_device: InputDevice,
    config: AppConfig,
    transcript_path: Path | None,
    audio_path: Path | None,
    errors: list[str],
    transcript_rejections: dict[str, int | dict[str, int]] | None = None,
) -> SessionMetadata:
    """設定・デバイス・実行結果を `SessionMetadata` に集約する。"""
    processing_seconds = (ended_at - started_at).total_seconds() if ended_at else None
    return SessionMetadata(
        started_at=started_at.replace(microsecond=0),
        ended_at=ended_at.replace(microsecond=0) if ended_at else None,
        input_device_name=input_device.name,
        input_device_index=input_device.index,
        sample_rate=config.audio.sample_rate,
        chunk_seconds=config.audio.chunk_seconds,
        whisper_model=config.transcription.whisper_model,
        ollama_model=config.summarization.ollama_model,
        language=config.transcription.language,
        transcript_path=transcript_path,
        audio_path=audio_path,
        transcript_rejections=transcript_rejections or {"total": 0, "by_reason": {}},
        errors=errors,
        processing_seconds=processing_seconds,
    )


def write_metadata(path: Path, metadata: SessionMetadata) -> None:
    """`metadata` を JSON として `path` に書き出す。"""
    data = metadata.model_dump(mode="json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
