import logging
from datetime import datetime

from rich.console import Console

from meeting_minutes.audio_stream import audio_chunks
from meeting_minutes.config import AppConfig
from meeting_minutes.dedupe import TranscriptDedupe
from meeting_minutes.devices import resolve_input_device
from meeting_minutes.metadata import build_metadata, write_metadata
from meeting_minutes.output import (
    append_transcript,
    create_session_dir,
    format_elapsed,
    init_transcript,
)
from meeting_minutes.summarize import generate_minutes
from meeting_minutes.transcribe import WhisperTranscriber

console = Console()
logger = logging.getLogger(__name__)


def run_live(config: AppConfig, *, draft_interval_minutes: int = 0) -> None:
    started_at = datetime.now()
    input_device = resolve_input_device(config.audio.device, config.audio.device_index)
    session_dir = create_session_dir(config.output.base_dir, started_at)
    transcript_path = session_dir / "transcript_live.md" if config.output.save_transcript else None
    errors: list[str] = []

    if transcript_path is not None:
        init_transcript(transcript_path, config, input_device, started_at)

    console.print(f"[green]Recording:[/green] {input_device.name} [{input_device.index}]")
    console.print(f"[green]Output:[/green] {session_dir}")
    console.print("Press Ctrl+C to stop.")

    transcriber = WhisperTranscriber(config.transcription)
    dedupe = TranscriptDedupe()
    elapsed_seconds = 0
    interval_seconds = draft_interval_minutes * 60
    next_draft_at = interval_seconds if interval_seconds > 0 else None

    try:
        for chunk in audio_chunks(
            device_index=input_device.index,
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            chunk_seconds=config.audio.chunk_seconds,
        ):
            elapsed_seconds += config.audio.chunk_seconds
            text = transcriber.transcribe(chunk)
            if not dedupe.should_keep(text):
                continue
            stamp = format_elapsed(elapsed_seconds)
            console.print(f"[cyan][{stamp}][/cyan] {text}")
            if transcript_path is not None:
                append_transcript(transcript_path, elapsed_seconds, text)

            if (
                next_draft_at is not None
                and transcript_path is not None
                and elapsed_seconds >= next_draft_at
            ):
                try:
                    generate_minutes(
                        transcript_path,
                        "draft",
                        session_dir / "minutes_draft.md",
                        config,
                    )
                except Exception as exc:  # keep realtime transcription alive
                    logger.exception("Draft generation failed")
                    errors.append(f"draft generation failed: {exc}")
                next_draft_at += interval_seconds
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
    except Exception as exc:
        logger.exception("Live session aborted")
        errors.append(str(exc))
        raise
    finally:
        ended_at = datetime.now()
        metadata = build_metadata(
            started_at=started_at,
            ended_at=ended_at,
            input_device=input_device,
            config=config,
            transcript_path=transcript_path,
            errors=errors,
        )
        write_metadata(session_dir / "metadata.json", metadata)
        console.print(f"[green]Metadata saved:[/green] {session_dir / 'metadata.json'}")
