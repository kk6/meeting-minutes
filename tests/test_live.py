import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from meeting_minutes.audio.devices import InputDevice
from meeting_minutes.audio.stream import AudioOverflowError
from meeting_minutes.config import AppConfig, AudioConfig, OutputConfig, PreprocessingConfig
from meeting_minutes.transcription.live import DraftScheduler, _segment_elapsed_range, run_live
from meeting_minutes.transcription.transcribe import TranscriptionSegment


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

    monkeypatch.setattr("meeting_minutes.transcription.live.audio_chunks", fake_audio_chunks)


@pytest.fixture
def fake_transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTranscriber:
        def __init__(self, _config: object, *, initial_prompt: object = None) -> None:
            pass

        def transcribe_segments(
            self,
            _chunk: np.ndarray,
            *,
            initial_prompt: str | None = None,
        ) -> list[TranscriptionSegment]:
            return [TranscriptionSegment(start=0.1, end=0.9, text="hello")]

    monkeypatch.setattr("meeting_minutes.transcription.live.WhisperTranscriber", FakeTranscriber)


@pytest.fixture
def live_dependencies(
    input_device: InputDevice,
    single_chunk_audio: None,
    fake_transcriber: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "meeting_minutes.transcription.live.resolve_input_device", lambda *_args: input_device
    )


def live_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        audio=AudioConfig(chunk_seconds=1),
        output=OutputConfig(base_dir=tmp_path),
    )


def test_segment_elapsed_range_encloses_segment_times() -> None:
    segment = TranscriptionSegment(start=0.51, end=1.49, text="hello")

    assert _segment_elapsed_range(10, segment) == (10, 12)


def test_draft_scheduler_generates_when_transcript_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript_path = tmp_path / "transcript_live.md"
    transcript_path.write_text("# transcript\n", encoding="utf-8")
    calls: list[Path] = []

    def fake_generate_minutes(
        transcript_file: Path,
        _mode: object,
        _output: object,
        _config: object,
    ) -> Path:
        calls.append(transcript_file)
        return tmp_path / "minutes_draft.md"

    monkeypatch.setattr(
        "meeting_minutes.transcription.live.generate_minutes", fake_generate_minutes
    )
    scheduler = DraftScheduler.create(
        draft_interval_minutes=1,
        transcript_path=transcript_path,
        session_dir=tmp_path,
        config=live_config(tmp_path),
        errors=[],
    )

    transcript_path.write_text("# transcript\nhello\n", encoding="utf-8")
    scheduler.maybe_generate(60)
    scheduler.maybe_generate(120)

    assert calls == [transcript_path]


def test_run_live_writes_audio_and_transcript(
    tmp_path: Path,
    live_dependencies: None,
) -> None:
    run_live(live_config(tmp_path))

    transcript = next(tmp_path.glob("*/transcript_live.md")).read_text(encoding="utf-8")
    audio_path = next(tmp_path.glob("*/audio_live.wav"))
    assert "[00:00:00 - 00:00:01] hello" in transcript
    assert audio_path.stat().st_size > 44


def test_run_live_applies_preprocessing_before_transcription(
    tmp_path: Path,
    input_device: InputDevice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_peaks: list[float] = []

    def fake_audio_chunks(**_kwargs: object) -> Iterator[np.ndarray]:
        yield np.full(16000, 0.1, dtype=np.float32)

    class FakeTranscriber:
        def __init__(self, _config: object, *, initial_prompt: object = None) -> None:
            pass

        def transcribe_segments(
            self,
            chunk: np.ndarray,
            *,
            initial_prompt: str | None = None,
        ) -> list[TranscriptionSegment]:
            captured_peaks.append(float(np.max(np.abs(chunk))))
            return [TranscriptionSegment(start=0.1, end=0.9, text="hello")]

    monkeypatch.setattr(
        "meeting_minutes.transcription.live.resolve_input_device", lambda *_args: input_device
    )
    monkeypatch.setattr("meeting_minutes.transcription.live.audio_chunks", fake_audio_chunks)
    monkeypatch.setattr("meeting_minutes.transcription.live.WhisperTranscriber", FakeTranscriber)

    config = AppConfig(
        audio=AudioConfig(chunk_seconds=1),
        output=OutputConfig(base_dir=tmp_path),
        preprocessing=PreprocessingConfig(enabled=True, target_peak=0.5),
    )

    run_live(config)

    assert captured_peaks == [pytest.approx(0.5)]


def test_run_live_continues_when_audio_writer_cannot_open(
    tmp_path: Path,
    live_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenAudioWriter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

    monkeypatch.setattr("meeting_minutes.transcription.live.WavAudioWriter", BrokenAudioWriter)

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

    monkeypatch.setattr("meeting_minutes.transcription.live.WavAudioWriter", BrokenAudioWriter)

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

    monkeypatch.setattr("meeting_minutes.transcription.live.WavAudioWriter", BrokenAudioWriter)

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

    monkeypatch.setattr(
        "meeting_minutes.transcription.live.resolve_input_device", lambda *_args: input_device
    )
    monkeypatch.setattr("meeting_minutes.transcription.live.audio_chunks", fake_audio_chunks)

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


def test_run_live_stops_when_stop_event_is_set(
    tmp_path: Path,
    input_device: InputDevice,
    fake_transcriber: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    stop_event = threading.Event()
    chunks_seen = 0

    def fake_audio_chunks(**_kwargs: object) -> Iterator[np.ndarray]:
        nonlocal chunks_seen
        while True:
            chunks_seen += 1
            yield np.full(16000, 0.1, dtype=np.float32)

    monkeypatch.setattr(
        "meeting_minutes.transcription.live.resolve_input_device", lambda *_args: input_device
    )
    monkeypatch.setattr("meeting_minutes.transcription.live.audio_chunks", fake_audio_chunks)
    stop_event.set()

    run_live(live_config(tmp_path), stop_event=stop_event)

    assert chunks_seen == 1


def test_run_live_aborts_on_audio_overflow_by_default(
    tmp_path: Path,
    input_device: InputDevice,
    fake_transcriber: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_audio_chunks(*, abort_on_overflow: bool, **_kwargs: object) -> Iterator[np.ndarray]:
        assert abort_on_overflow
        raise AudioOverflowError("音声入力の処理が追いつかず、1 block(s) を取り逃がしました。")

    monkeypatch.setattr(
        "meeting_minutes.transcription.live.resolve_input_device", lambda *_args: input_device
    )
    monkeypatch.setattr("meeting_minutes.transcription.live.audio_chunks", fake_audio_chunks)

    with pytest.raises(AudioOverflowError):
        run_live(live_config(tmp_path))

    session_dir = next(tmp_path.glob("*_live_meeting"))
    metadata = (session_dir / "metadata.json").read_text(encoding="utf-8")
    assert "1 block(s) を取り逃がしました" in metadata
