import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from meeting_minutes.audio_stream import AudioOverflowError
from meeting_minutes.config import AppConfig, AudioConfig, OutputConfig
from meeting_minutes.devices import InputDevice
from meeting_minutes.live import _segment_elapsed_range, run_live
from meeting_minutes.transcribe import TranscriptionSegment


@pytest.fixture
def input_device() -> InputDevice:
    return InputDevice(
        index=1,
        name="Mic",
        channels=1,
        default_sample_rate=16000,
        is_blackhole=False,
    )


@pytest.fixture
def single_chunk_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_audio_chunks(**_kwargs: object) -> Iterator[np.ndarray]:
        yield np.full(16000, 0.1, dtype=np.float32)

    monkeypatch.setattr("meeting_minutes.live.audio_chunks", fake_audio_chunks)


@pytest.fixture
def fake_transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTranscriber:
        def __init__(self, _config: object, *, initial_prompt: object = None) -> None:
            pass

        def transcribe_segments(self, _chunk: np.ndarray) -> list[TranscriptionSegment]:
            return [TranscriptionSegment(start=0.1, end=0.9, text="hello")]

    monkeypatch.setattr("meeting_minutes.live.WhisperTranscriber", FakeTranscriber)


@pytest.fixture
def live_dependencies(
    input_device: InputDevice,
    single_chunk_audio: None,
    fake_transcriber: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("meeting_minutes.live.resolve_input_device", lambda *_args: input_device)


def live_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        audio=AudioConfig(chunk_seconds=1),
        output=OutputConfig(base_dir=tmp_path),
    )


def test_segment_elapsed_range_encloses_segment_times() -> None:
    segment = TranscriptionSegment(start=0.51, end=1.49, text="hello")

    assert _segment_elapsed_range(10, segment) == (10, 12)


def test_run_live_writes_audio_and_transcript(
    tmp_path: Path,
    live_dependencies: None,
) -> None:
    run_live(live_config(tmp_path))

    transcript = next(tmp_path.glob("*/transcript_live.md")).read_text(encoding="utf-8")
    audio_path = next(tmp_path.glob("*/audio_live.wav"))
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert audio_path.stat().st_size > 44


def test_run_live_continues_when_audio_writer_cannot_open(
    tmp_path: Path,
    live_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenAudioWriter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

    monkeypatch.setattr("meeting_minutes.live.WavAudioWriter", BrokenAudioWriter)

    run_live(live_config(tmp_path))

    session_dir = next(tmp_path.glob("*_live_meeting"))
    transcript = (session_dir / "transcript_live.md").read_text(encoding="utf-8")
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert "audio recording disabled: disk full" in metadata


def test_run_live_continues_when_audio_writer_write_fails(
    tmp_path: Path,
    live_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenAudioWriter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def write(self, _chunk: np.ndarray) -> None:
            raise OSError("disk full")

        def close(self) -> None:
            pass

    monkeypatch.setattr("meeting_minutes.live.WavAudioWriter", BrokenAudioWriter)

    run_live(live_config(tmp_path))

    session_dir = next(tmp_path.glob("*_live_meeting"))
    transcript = (session_dir / "transcript_live.md").read_text(encoding="utf-8")
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert "audio recording disabled: disk full" in metadata


def test_run_live_writes_metadata_when_audio_writer_close_fails(
    tmp_path: Path,
    live_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenAudioWriter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def write(self, _chunk: np.ndarray) -> None:
            pass

        def close(self) -> None:
            raise OSError("flush failed")

    monkeypatch.setattr("meeting_minutes.live.WavAudioWriter", BrokenAudioWriter)

    run_live(live_config(tmp_path))

    session_dir = next(tmp_path.glob("*_live_meeting"))
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "audio recording close failed: flush failed" in metadata


def test_run_live_continues_and_records_audio_overflow_when_configured(
    tmp_path: Path,
    input_device: InputDevice,
    fake_transcriber: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_audio_chunks(
        *,
        abort_on_overflow: bool,
        on_overflow: object,
        **_kwargs: object,
    ) -> Iterator[np.ndarray]:
        assert not abort_on_overflow
        assert callable(on_overflow)
        on_overflow(1)
        on_overflow(2)
        yield np.full(16000, 0.1, dtype=np.float32)

    monkeypatch.setattr("meeting_minutes.live.resolve_input_device", lambda *_args: input_device)
    monkeypatch.setattr("meeting_minutes.live.audio_chunks", fake_audio_chunks)

    config = AppConfig(
        audio=AudioConfig(chunk_seconds=1, abort_on_overflow=False),
        output=OutputConfig(base_dir=tmp_path),
    )
    run_live(config)

    session_dir = next(tmp_path.glob("*_live_meeting"))
    transcript = (session_dir / "transcript_live.md").read_text(encoding="utf-8")
    metadata = json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert metadata["errors"] == [
        "音声入力の処理が追いつかず、合計 3 block(s) を 2 event(s) で取り逃がしました。"
    ]


def test_run_live_aborts_on_audio_overflow_by_default(
    tmp_path: Path,
    input_device: InputDevice,
    fake_transcriber: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_audio_chunks(*, abort_on_overflow: bool, **_kwargs: object) -> Iterator[np.ndarray]:
        assert abort_on_overflow
        raise AudioOverflowError("音声入力の処理が追いつかず、1 block(s) を取り逃がしました。")

    monkeypatch.setattr("meeting_minutes.live.resolve_input_device", lambda *_args: input_device)
    monkeypatch.setattr("meeting_minutes.live.audio_chunks", fake_audio_chunks)

    with pytest.raises(AudioOverflowError):
        run_live(live_config(tmp_path))

    session_dir = next(tmp_path.glob("*_live_meeting"))
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "1 block(s) を取り逃がしました" in metadata
