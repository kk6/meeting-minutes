"""ライブ録音セッションのオーケストレーション（録音・書き起こし・ドラフト生成）。"""

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
from meeting_minutes.live_transcription import SpeechTranscriptionRunner
from meeting_minutes.metadata import build_metadata, write_metadata
from meeting_minutes.output import (
    append_transcript_segment,
    create_session_dir,
    format_elapsed,
    init_transcript,
)
from meeting_minutes.preprocess import AudioPreprocessor
from meeting_minutes.summarize import generate_minutes
from meeting_minutes.transcribe import TranscriptionSegment, WhisperTranscriber
from meeting_minutes.transcript_filter import TranscriptFilter, TranscriptRejectionStats
from meeting_minutes.vad import SpeechSegmenter
from meeting_minutes.vocabulary import (
    RecentTranscriptContext,
    Vocabulary,
    build_contextual_initial_prompt,
    build_initial_prompt,
    load_vocabulary,
)

console = Console()
logger = logging.getLogger(__name__)
AUDIO_RECORDING_ERRORS: tuple[type[Exception], ...] = (OSError, ValueError, wave.Error)


def _segment_elapsed_range(
    chunk_start_seconds: float,
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
    """WAV 書き出し器のライフサイクルを管理し、エラー発生時は自動で録音を停止する。"""

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
    """音声入力オーバーフローの累計を記録し、`errors` 配列の同一エントリを更新する。"""

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
class DynamicPromptContext:
    """語彙ヒントと直近の文字起こし文脈を結合した initial_prompt を逐次生成する。"""

    vocabulary: Vocabulary
    max_prompt_chars: int
    recent_context_chars: int
    recent_context: RecentTranscriptContext

    def build(self) -> str | None:
        return build_contextual_initial_prompt(
            self.vocabulary,
            recent_context=self.recent_context.text,
            max_chars=self.max_prompt_chars,
            recent_context_chars=self.recent_context_chars,
        )

    def append(self, text: str) -> None:
        self.recent_context.append(text)


@dataclass
class TranscriptWriter:
    """確定セグメントをコンソールへ表示し、設定があればファイルへも追記する出力シンク。"""

    path: Path | None

    def write_segments(
        self,
        segments: list[TranscriptionSegment],
        *,
        chunk_start_seconds: float,
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
    """一定間隔で議事録ドラフトを生成するスケジューラ（文字起こしに更新がない場合はスキップ）。"""

    transcript_path: Path | None
    session_dir: Path
    config: AppConfig
    errors: list[str]
    interval_seconds: int
    next_draft_at: int | None
    last_draft_transcript_size: int

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
        transcript_size = cls._transcript_size(transcript_path) or 0
        return cls(
            transcript_path=transcript_path,
            session_dir=session_dir,
            config=config,
            errors=errors,
            interval_seconds=interval_seconds,
            next_draft_at=next_draft_at,
            last_draft_transcript_size=transcript_size,
        )

    def maybe_generate(self, elapsed_seconds: int) -> None:
        if self.next_draft_at is None or self.transcript_path is None:
            return
        if elapsed_seconds < self.next_draft_at:
            return
        transcript_size = self._transcript_size(self.transcript_path)
        if transcript_size is not None and transcript_size <= self.last_draft_transcript_size:
            self.next_draft_at += self.interval_seconds
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
        else:
            if transcript_size is not None:
                self.last_draft_transcript_size = transcript_size
        self.next_draft_at += self.interval_seconds

    @staticmethod
    def _transcript_size(transcript_path: Path | None) -> int | None:
        if transcript_path is None:
            return None
        try:
            return transcript_path.stat().st_size
        except OSError:
            return None


def run_live(config: AppConfig, *, draft_interval_minutes: int = 0) -> None:
    """ライブ録音セッションを起動する。

    `draft_interval_minutes > 0` でその間隔ごとに議事録ドラフトを生成する。
    """
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
    rejection_stats = TranscriptRejectionStats()
    transcript_filter = TranscriptFilter(config.transcript_filter, stats=rejection_stats)
    dedupe = TranscriptDedupe(stats=rejection_stats)
    speech_segmenter = SpeechSegmenter(config.vad, sample_rate=config.audio.sample_rate)
    prompt_context = (
        DynamicPromptContext(
            vocabulary=vocabulary,
            max_prompt_chars=config.vocabulary.max_prompt_chars,
            recent_context_chars=config.vocabulary.dynamic_context_chars,
            recent_context=RecentTranscriptContext(
                max_chars=config.vocabulary.dynamic_context_chars,
            ),
        )
        if config.vocabulary.dynamic_context_enabled
        else None
    )
    transcript_writer = TranscriptWriter(transcript_path)
    transcription_runner = SpeechTranscriptionRunner(
        speech_segmenter=speech_segmenter,
        transcriber=transcriber,
        dedupe=dedupe,
        transcript_filter=transcript_filter,
        segment_writer=transcript_writer,
        prompt_context=prompt_context,
    )
    audio_preprocessor = AudioPreprocessor(config.preprocessing)
    overflow_recorder = AudioOverflowRecorder(errors)
    draft_scheduler = DraftScheduler.create(
        draft_interval_minutes=draft_interval_minutes,
        transcript_path=transcript_path,
        session_dir=session_dir,
        config=config,
        errors=errors,
    )
    elapsed_seconds = 0
    if config.vad.enabled:
        console.print("[green]VAD:[/green] enabled")

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
            elapsed_seconds += config.audio.chunk_seconds
            audio_recording.write(chunk, errors)
            transcription_runner.process(audio_preprocessor.process(chunk))
            draft_scheduler.maybe_generate(elapsed_seconds)
        if transcription_runner.flush():
            draft_scheduler.maybe_generate(elapsed_seconds)
    except KeyboardInterrupt:
        if transcription_runner.flush():
            draft_scheduler.maybe_generate(elapsed_seconds)
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
            transcript_rejections=rejection_stats.as_dict(),
        )
        write_metadata(session_dir / "metadata.json", metadata)
        console.print(f"[green]Metadata saved:[/green] {session_dir / 'metadata.json'}")
