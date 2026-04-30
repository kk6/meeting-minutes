import logging
import wave
from dataclasses import dataclass
from datetime import datetime
from math import ceil, floor
from pathlib import Path

import numpy as np
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


@dataclass
class AudioRecording:
    path: Path | None
    writer: WavAudioWriter | None = None

    @classmethod
    def open(cls, path: Path | None, *, sample_rate: int, errors: list[str]) -> "AudioRecording":
        if path is None:
            return cls(path=None)
        try:
            writer = WavAudioWriter(path, sample_rate=sample_rate)
        except AUDIO_RECORDING_ERRORS as exc:
            logger.exception("Audio recording disabled")
            errors.append(f"audio recording disabled: {exc}")
            return cls(path=None)
        return cls(path=path, writer=writer)

    def write(self, chunk: np.ndarray, errors: list[str]) -> None:
        if self.writer is None:
            return
        try:
            self.writer.write(chunk)
        except AUDIO_RECORDING_ERRORS as exc:
            logger.exception("Audio recording disabled")
            errors.append(f"audio recording disabled: {exc}")
            _close_audio_writer(self.writer, errors)
            self.writer = None
            self.path = None

    def close(self, errors: list[str]) -> None:
        if self.writer is not None:
            _close_audio_writer(self.writer, errors)
            self.writer = None


@dataclass
class AudioOverflowRecorder:
    errors: list[str]
    events: int = 0
    blocks: int = 0
    error_index: int | None = None

    def record(self, dropped_blocks: int) -> None:
        self.events += 1
        self.blocks += dropped_blocks
        message = (
            "音声入力の処理が追いつかず、"
            f"合計 {self.blocks} block(s) を {self.events} event(s) で取り逃がしました。"
        )
        if self.error_index is None:
            self.error_index = len(self.errors)
            self.errors.append(message)
        else:
            self.errors[self.error_index] = message

        if self.events == 1 or self.events % 10 == 0:
            logger.warning(message)
            console.print(f"[yellow]{message} 続行します。[/yellow]")


@dataclass
class TranscriptWriter:
    path: Path | None

    def write_segments(
        self,
        segments: list[TranscriptionSegment],
        *,
        chunk_start_seconds: int,
    ) -> None:
        for segment in segments:
            segment_start, segment_elapsed = _segment_elapsed_range(
                chunk_start_seconds,
                segment,
            )
            stamp = format_elapsed(segment_elapsed)
            console.print(f"[cyan][{stamp}][/cyan] {segment.text}")
            if self.path is not None:
                append_transcript_segment(
                    self.path,
                    segment_start,
                    segment_elapsed,
                    segment.text,
                )


@dataclass
class DraftScheduler:
    transcript_path: Path | None
    session_dir: Path
    config: AppConfig
    errors: list[str]
    interval_seconds: int
    next_draft_at: int | None

    @classmethod
    def create(
        cls,
        *,
        draft_interval_minutes: int,
        transcript_path: Path | None,
        session_dir: Path,
        config: AppConfig,
        errors: list[str],
    ) -> "DraftScheduler":
        interval_seconds = draft_interval_minutes * 60
        next_draft_at = interval_seconds if interval_seconds > 0 else None
        return cls(
            transcript_path=transcript_path,
            session_dir=session_dir,
            config=config,
            errors=errors,
            interval_seconds=interval_seconds,
            next_draft_at=next_draft_at,
        )

    def maybe_generate(self, elapsed_seconds: int) -> None:
        if self.next_draft_at is None or self.transcript_path is None:
            return
        if elapsed_seconds < self.next_draft_at:
            return

        try:
            generate_minutes(
                self.transcript_path,
                "draft",
                self.session_dir / "minutes_draft.md",
                self.config,
            )
        except (MeetingMinutesError, OSError, UnicodeError) as exc:
            logger.exception("Draft generation failed")
            self.errors.append(f"draft generation failed: {exc}")
        self.next_draft_at += self.interval_seconds


def run_live(config: AppConfig, *, draft_interval_minutes: int = 0) -> None:
    started_at = datetime.now()
    input_device = resolve_input_device(config.audio.device, config.audio.device_index)
    session_dir = create_session_dir(config.output.base_dir, started_at)
    transcript_path = session_dir / "transcript_live.md" if config.output.save_transcript else None
    audio_path = session_dir / "audio_live.wav" if config.output.save_audio else None
    audio_recording = AudioRecording(path=audio_path)
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
    transcript_writer = TranscriptWriter(transcript_path)
    overflow_recorder = AudioOverflowRecorder(errors)
    draft_scheduler = DraftScheduler.create(
        draft_interval_minutes=draft_interval_minutes,
        transcript_path=transcript_path,
        session_dir=session_dir,
        config=config,
        errors=errors,
    )
    elapsed_seconds = 0

    try:
        audio_recording = AudioRecording.open(
            audio_path,
            sample_rate=config.audio.sample_rate,
            errors=errors,
        )

        for chunk in audio_chunks(
            device_index=input_device.index,
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            chunk_seconds=config.audio.chunk_seconds,
            abort_on_overflow=config.audio.abort_on_overflow,
            on_overflow=overflow_recorder.record,
        ):
            chunk_start_seconds = elapsed_seconds
            elapsed_seconds += config.audio.chunk_seconds
            audio_recording.write(chunk, errors)
            segments = transcriber.transcribe_segments(chunk)
            text = " ".join(segment.text for segment in segments).strip()
            if not dedupe.should_keep(text):
                continue
            transcript_writer.write_segments(
                segments,
                chunk_start_seconds=chunk_start_seconds,
            )
            draft_scheduler.maybe_generate(elapsed_seconds)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
    except Exception as exc:
        logger.exception("Live session aborted")
        errors.append(str(exc))
        raise
    finally:
        audio_recording.close(errors)
        ended_at = datetime.now()
        metadata = build_metadata(
            started_at=started_at,
            ended_at=ended_at,
            input_device=input_device,
            config=config,
            transcript_path=transcript_path,
            audio_path=audio_recording.path,
            errors=errors,
        )
        write_metadata(session_dir / "metadata.json", metadata)
        console.print(f"[green]Metadata saved:[/green] {session_dir / 'metadata.json'}")
