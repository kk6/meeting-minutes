from datetime import datetime
from pathlib import Path

from meeting_minutes.config import AppConfig
from meeting_minutes.devices import InputDevice


def create_session_dir(base_dir: Path, started_at: datetime) -> Path:
    session = base_dir / f"{started_at:%Y-%m-%d_%H%M%S}_live_meeting"
    session.mkdir(parents=True, exist_ok=True)
    return session


def format_elapsed(elapsed_seconds: int) -> str:
    return (
        f"{elapsed_seconds // 3600:02d}:"
        f"{elapsed_seconds % 3600 // 60:02d}:"
        f"{elapsed_seconds % 60:02d}"
    )


def init_transcript(
    path: Path,
    config: AppConfig,
    input_device: InputDevice,
    started_at: datetime,
) -> None:
    path.write_text(
        "\n".join(
            [
                "# Live Transcript",
                "",
                "## Metadata",
                "",
                f"- Started at: {started_at:%Y-%m-%d %H:%M:%S}",
                f"- Input device: {input_device.name}",
                f"- Input device index: {input_device.index}",
                f"- Language: {config.transcription.language}",
                f"- Whisper model: {config.transcription.whisper_model}",
                "",
                "## Body",
                "",
            ]
        ),
        encoding="utf-8",
    )


def append_transcript_segment(
    path: Path,
    start_seconds: int,
    end_seconds: int,
    text: str,
) -> None:
    with path.open("a", encoding="utf-8") as file:
        start_stamp = format_elapsed(start_seconds)
        end_stamp = format_elapsed(end_seconds)
        file.write(f"[{start_stamp} - {end_stamp}] {text}\n")
