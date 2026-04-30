import numpy as np

from meeting_minutes.config import VadConfig
from meeting_minutes.dedupe import TranscriptDedupe
from meeting_minutes.live_transcription import SpeechTranscriptionRunner
from meeting_minutes.transcribe import TranscriptionSegment
from meeting_minutes.vad import SpeechSegmenter


class FakeTranscriber:
    def transcribe_segments(self, _audio: np.ndarray) -> list[TranscriptionSegment]:
        return [TranscriptionSegment(start=0, end=0.2, text="hello")]


class SegmentCollector:
    def __init__(self) -> None:
        self.calls: list[tuple[float, list[TranscriptionSegment]]] = []

    def write_segments(
        self,
        segments: list[TranscriptionSegment],
        *,
        chunk_start_seconds: float,
    ) -> None:
        self.calls.append((chunk_start_seconds, segments))


def test_speech_transcription_runner_writes_detected_speech() -> None:
    collector = SegmentCollector()
    runner = SpeechTranscriptionRunner(
        speech_segmenter=SpeechSegmenter(
            VadConfig(
                frame_ms=100,
                silence_seconds=0.2,
                min_speech_seconds=0.1,
                padding_seconds=0,
            ),
            sample_rate=10,
        ),
        transcriber=FakeTranscriber(),
        dedupe=TranscriptDedupe(),
        segment_writer=collector,
    )

    wrote_during_process = runner.process(
        np.concatenate((np.full(2, 0.1, dtype=np.float32), np.zeros(3, dtype=np.float32)))
    )

    assert wrote_during_process
    assert len(collector.calls) == 1
    assert collector.calls[0][0] == 0
    assert collector.calls[0][1][0].text == "hello"


def test_speech_transcription_runner_flushes_pending_speech() -> None:
    collector = SegmentCollector()
    runner = SpeechTranscriptionRunner(
        speech_segmenter=SpeechSegmenter(
            VadConfig(frame_ms=100, min_speech_seconds=0.1, padding_seconds=0),
            sample_rate=10,
        ),
        transcriber=FakeTranscriber(),
        dedupe=TranscriptDedupe(),
        segment_writer=collector,
    )

    assert not runner.process(np.full(2, 0.1, dtype=np.float32))
    assert runner.flush()
    assert len(collector.calls) == 1


def test_speech_transcription_runner_passthrough_when_vad_is_disabled() -> None:
    collector = SegmentCollector()
    runner = SpeechTranscriptionRunner(
        speech_segmenter=SpeechSegmenter(VadConfig(enabled=False), sample_rate=10),
        transcriber=FakeTranscriber(),
        dedupe=TranscriptDedupe(),
        segment_writer=collector,
    )

    assert runner.process(np.full(2, 0.1, dtype=np.float32))
    assert len(collector.calls) == 1
    assert collector.calls[0][0] == 0
