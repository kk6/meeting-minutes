from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from meeting_minutes.config import AppConfig, AudioConfig, OutputConfig
from meeting_minutes.devices import InputDevice
from meeting_minutes.live import run_live
from meeting_minutes.transcribe import TranscriptionSegment


def test_run_live_rounds_segment_timestamp_to_nearest_second(
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
        def __init__(self, _config: object) -> None:
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
    assert "[00:00:01] hello" in transcript
