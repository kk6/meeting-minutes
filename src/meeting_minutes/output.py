from datetime import datetime
from pathlib import Path

from meeting_minutes.config import AppConfig
from meeting_minutes.devices import InputDevice


def create_session_dir(base_dir: Path, started_at: datetime) -> Path:
    session = base_dir / f"{started_at:%Y-%m-%d_%H%M%S}_live_meeting"
    session.mkdir(parents=True, exist_ok=True)
    (session / "chunks").mkdir(exist_ok=True)
    (session / "summaries").mkdir(exist_ok=True)
    return session


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


def append_transcript(path: Path, elapsed_seconds: int, text: str) -> None:
    with path.open("a", encoding="utf-8") as file:
        stamp = (
            f"{elapsed_seconds // 3600:02}:"
            f"{elapsed_seconds % 3600 // 60:02}:"
            f"{elapsed_seconds % 60:02}"
        )
        file.write(f"[{stamp}] {text}\n")
