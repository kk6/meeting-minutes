import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from meeting_minutes.config import AppConfig
from meeting_minutes.devices import InputDevice


class SessionMetadata(BaseModel):
    started_at: str
    ended_at: str | None = None
    input_device_name: str
    input_device_index: int
    sample_rate: int
    chunk_seconds: int
    whisper_model: str
    ollama_model: str
    language: str
    transcript_path: str | None
    errors: list[str]
    processing_seconds: float | None = None


def build_metadata(
    *,
    started_at: datetime,
    ended_at: datetime | None,
    input_device: InputDevice,
    config: AppConfig,
    transcript_path: Path | None,
    errors: list[str],
) -> SessionMetadata:
    processing_seconds = (ended_at - started_at).total_seconds() if ended_at else None
    return SessionMetadata(
        started_at=started_at.isoformat(timespec="seconds"),
        ended_at=ended_at.isoformat(timespec="seconds") if ended_at else None,
        input_device_name=input_device.name,
        input_device_index=input_device.index,
        sample_rate=config.audio.sample_rate,
        chunk_seconds=config.audio.chunk_seconds,
        whisper_model=config.transcription.whisper_model,
        ollama_model=config.summarization.ollama_model,
        language=config.transcription.language,
        transcript_path=str(transcript_path) if transcript_path else None,
        errors=errors,
        processing_seconds=processing_seconds,
    )


def write_metadata(path: Path, metadata: SessionMetadata) -> None:
    data: dict[str, Any] = metadata.model_dump()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
