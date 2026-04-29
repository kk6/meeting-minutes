import logging
import wave
from datetime import datetime
from math import ceil, floor

from rich.console import Console

from meeting_minutes.audio_output import WavAudioWriter
from meeting_minutes.audio_stream import audio_chunks
from meeting_minutes.config import AppConfig
from meeting_minutes.dedupe import TranscriptDedupe
from meeting_minutes.devices import resolve_input_device
from meeting_minutes.errors import MeetingMinutesError
from meeting_minutes.metadata import build_metadata, write_metadata
from meeting_minutes.output import (
    append_transcript_segment,
    create_session_dir,
    format_elapsed,
    init_transcript,
)
from meeting_minutes.summarize import generate_minutes
from meeting_minutes.transcribe import TranscriptionSegment, WhisperTranscriber
from meeting_minutes.vocabulary import build_initial_prompt, load_vocabulary

console = Console()
logger = logging.getLogger(__name__)
AUDIO_RECORDING_ERRORS: tuple[type[Exception], ...] = (OSError, ValueError, wave.Error)


def _segment_elapsed_range(
    chunk_start_seconds: int,
    segment: TranscriptionSegment,
) -> tuple[int, int]:
    start = floor(chunk_start_seconds + segment.start)
    end = ceil(chunk_start_seconds + segment.end)
    return start, max(start, end)


def _close_audio_writer(audio_writer: WavAudioWriter, errors: list[str]) -> None:
    try:
        audio_writer.close()
    except AUDIO_RECORDING_ERRORS as exc:
        logger.exception("Failed to close audio writer")
        errors.append(f"audio recording close failed: {exc}")


def run_live(config: AppConfig, *, draft_interval_minutes: int = 0) -> None:
    started_at = datetime.now()
    input_device = resolve_input_device(config.audio.device, config.audio.device_index)
    session_dir = create_session_dir(config.output.base_dir, started_at)
    transcript_path = session_dir / "transcript_live.md" if config.output.save_transcript else None
    audio_path = session_dir / "audio_live.wav" if config.output.save_audio else None
    audio_writer: WavAudioWriter | None = None
    errors: list[str] = []

    if transcript_path is not None:
        init_transcript(transcript_path, config, input_device, started_at)

    console.print(f"[green]Recording:[/green] {input_device.name} [{input_device.index}]")
    console.print(f"[green]Output:[/green] {session_dir}")
    console.print("Press Ctrl+C to stop.")

    vocabulary = load_vocabulary(config.vocabulary)
    initial_prompt = build_initial_prompt(
        vocabulary,
        max_chars=config.vocabulary.max_prompt_chars,
    )
    if initial_prompt:
        console.print(f"[green]Vocabulary hint:[/green] {len(initial_prompt)} chars")
    transcriber = WhisperTranscriber(config.transcription, initial_prompt=initial_prompt)
    dedupe = TranscriptDedupe()
    elapsed_seconds = 0
    interval_seconds = draft_interval_minutes * 60
    next_draft_at = interval_seconds if interval_seconds > 0 else None

    try:
        if audio_path is not None:
            try:
                audio_writer = WavAudioWriter(audio_path, sample_rate=config.audio.sample_rate)
            except AUDIO_RECORDING_ERRORS as exc:
                logger.exception("Audio recording disabled")
                errors.append(f"audio recording disabled: {exc}")
                audio_path = None

        for chunk in audio_chunks(
            device_index=input_device.index,
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            chunk_seconds=config.audio.chunk_seconds,
        ):
            chunk_start_seconds = elapsed_seconds
            elapsed_seconds += config.audio.chunk_seconds
            if audio_writer is not None:
                try:
                    audio_writer.write(chunk)
                except AUDIO_RECORDING_ERRORS as exc:
                    logger.exception("Audio recording disabled")
                    errors.append(f"audio recording disabled: {exc}")
                    _close_audio_writer(audio_writer, errors)
                    audio_writer = None
                    audio_path = None
            segments = transcriber.transcribe_segments(chunk)
            text = " ".join(segment.text for segment in segments).strip()
            if not dedupe.should_keep(text):
                continue
            for segment in segments:
                segment_start, segment_elapsed = _segment_elapsed_range(
                    chunk_start_seconds,
                    segment,
                )
                stamp = format_elapsed(segment_elapsed)
                console.print(f"[cyan][{stamp}][/cyan] {segment.text}")
                if transcript_path is not None:
                    append_transcript_segment(
                        transcript_path,
                        segment_start,
                        segment_elapsed,
                        segment.text,
                    )

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
                except (MeetingMinutesError, OSError, UnicodeError) as exc:
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
        if audio_writer is not None:
            _close_audio_writer(audio_writer, errors)
        ended_at = datetime.now()
        metadata = build_metadata(
            started_at=started_at,
            ended_at=ended_at,
            input_device=input_device,
            config=config,
            transcript_path=transcript_path,
            audio_path=audio_path,
            errors=errors,
        )
        write_metadata(session_dir / "metadata.json", metadata)
        console.print(f"[green]Metadata saved:[/green] {session_dir / 'metadata.json'}")
