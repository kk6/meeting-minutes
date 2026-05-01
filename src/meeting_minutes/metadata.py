"""録音セッションの実行メタデータ（環境・成果物パス・統計）の構築と保存。"""

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from meeting_minutes.config import AppConfig
from meeting_minutes.devices import InputDevice


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
    """設定・デバイス・実行結果を 1 つの `SessionMetadata` に集約する。

    `ended_at` が None の場合は処理時間も None として保持する（途中終了を区別するため）。
    タイムスタンプは秒精度に丸め、JSON 化時の冗長な microsecond を抑止する。
    """
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
    """`metadata` を UTF-8 / インデント付き JSON として `path` へ書き出す。"""
    data = metadata.model_dump(mode="json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
