from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from meeting_minutes.config import AppConfig, AudioConfig, OutputConfig
from meeting_minutes.devices import InputDevice
from meeting_minutes.live import _segment_elapsed_range, run_live
from meeting_minutes.transcribe import TranscriptionSegment


def test_segment_elapsed_range_encloses_segment_times() -> None:
    segment = TranscriptionSegment(start=0.51, end=1.49, text="hello")

    assert _segment_elapsed_range(10, segment) == (10, 12)


def test_run_live_writes_audio_and_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_device = InputDevice(
        index=1,
        name="Mic",
        channels=1,
        default_sample_rate=16000,
        is_blackhole=False,
    )

    def fake_audio_chunks(**_kwargs: object) -> Iterator[np.ndarray]:
        yield np.zeros(16000, dtype=np.float32)

    class FakeTranscriber:
        def __init__(self, _config: object, *, initial_prompt: object = None) -> None:
            pass

        def transcribe_segments(self, _chunk: np.ndarray) -> list[TranscriptionSegment]:
            return [TranscriptionSegment(start=0.1, end=0.9, text="hello")]

    monkeypatch.setattr("meeting_minutes.live.resolve_input_device", lambda *_args: input_device)
    monkeypatch.setattr("meeting_minutes.live.audio_chunks", fake_audio_chunks)
    monkeypatch.setattr("meeting_minutes.live.WhisperTranscriber", FakeTranscriber)

    run_live(
        AppConfig(
            audio=AudioConfig(chunk_seconds=1),
            output=OutputConfig(base_dir=tmp_path),
        )
    )

    transcript = next(tmp_path.glob("*/transcript_live.md")).read_text(encoding="utf-8")
    audio_path = next(tmp_path.glob("*/audio_live.wav"))
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert audio_path.stat().st_size > 44


def test_run_live_continues_when_audio_writer_cannot_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_device = InputDevice(
        index=1,
        name="Mic",
        channels=1,
        default_sample_rate=16000,
        is_blackhole=False,
    )

    def fake_audio_chunks(**_kwargs: object) -> Iterator[np.ndarray]:
        yield np.zeros(16000, dtype=np.float32)

    class FakeTranscriber:
        def __init__(self, _config: object, *, initial_prompt: object = None) -> None:
            pass

        def transcribe_segments(self, _chunk: np.ndarray) -> list[TranscriptionSegment]:
            return [TranscriptionSegment(start=0.1, end=0.9, text="hello")]

    class BrokenAudioWriter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

    monkeypatch.setattr("meeting_minutes.live.resolve_input_device", lambda *_args: input_device)
    monkeypatch.setattr("meeting_minutes.live.audio_chunks", fake_audio_chunks)
    monkeypatch.setattr("meeting_minutes.live.WhisperTranscriber", FakeTranscriber)
    monkeypatch.setattr("meeting_minutes.live.WavAudioWriter", BrokenAudioWriter)

    run_live(
        AppConfig(
            audio=AudioConfig(chunk_seconds=1),
            output=OutputConfig(base_dir=tmp_path),
        )
    )

    session_dir = next(tmp_path.glob("*_live_meeting"))
    transcript = (session_dir / "transcript_live.md").read_text(encoding="utf-8")
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert "audio recording disabled: disk full" in metadata


def test_run_live_continues_when_audio_writer_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_device = InputDevice(
        index=1,
        name="Mic",
        channels=1,
        default_sample_rate=16000,
        is_blackhole=False,
    )

    def fake_audio_chunks(**_kwargs: object) -> Iterator[np.ndarray]:
        yield np.zeros(16000, dtype=np.float32)

    class FakeTranscriber:
        def __init__(self, _config: object, *, initial_prompt: object = None) -> None:
            pass

        def transcribe_segments(self, _chunk: np.ndarray) -> list[TranscriptionSegment]:
            return [TranscriptionSegment(start=0.1, end=0.9, text="hello")]

    class BrokenAudioWriter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def write(self, _chunk: np.ndarray) -> None:
            raise OSError("disk full")

        def close(self) -> None:
            pass

    monkeypatch.setattr("meeting_minutes.live.resolve_input_device", lambda *_args: input_device)
    monkeypatch.setattr("meeting_minutes.live.audio_chunks", fake_audio_chunks)
    monkeypatch.setattr("meeting_minutes.live.WhisperTranscriber", FakeTranscriber)
    monkeypatch.setattr("meeting_minutes.live.WavAudioWriter", BrokenAudioWriter)

    run_live(
        AppConfig(
            audio=AudioConfig(chunk_seconds=1),
            output=OutputConfig(base_dir=tmp_path),
        )
    )

    session_dir = next(tmp_path.glob("*_live_meeting"))
    transcript = (session_dir / "transcript_live.md").read_text(encoding="utf-8")
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert "audio recording disabled: disk full" in metadata


def test_run_live_writes_metadata_when_audio_writer_close_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_device = InputDevice(
        index=1,
        name="Mic",
        channels=1,
        default_sample_rate=16000,
        is_blackhole=False,
    )

    def fake_audio_chunks(**_kwargs: object) -> Iterator[np.ndarray]:
        yield np.zeros(16000, dtype=np.float32)

    class FakeTranscriber:
        def __init__(self, _config: object, *, initial_prompt: object = None) -> None:
            pass

        def transcribe_segments(self, _chunk: np.ndarray) -> list[TranscriptionSegment]:
            return [TranscriptionSegment(start=0.1, end=0.9, text="hello")]

    class BrokenAudioWriter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def write(self, _chunk: np.ndarray) -> None:
            pass

        def close(self) -> None:
            raise OSError("flush failed")

    monkeypatch.setattr("meeting_minutes.live.resolve_input_device", lambda *_args: input_device)
    monkeypatch.setattr("meeting_minutes.live.audio_chunks", fake_audio_chunks)
    monkeypatch.setattr("meeting_minutes.live.WhisperTranscriber", FakeTranscriber)
    monkeypatch.setattr("meeting_minutes.live.WavAudioWriter", BrokenAudioWriter)

    run_live(
        AppConfig(
            audio=AudioConfig(chunk_seconds=1),
            output=OutputConfig(base_dir=tmp_path),
        )
    )

    session_dir = next(tmp_path.glob("*_live_meeting"))
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "audio recording close failed: flush failed" in metadata
