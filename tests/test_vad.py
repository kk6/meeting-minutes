import numpy as np

from meeting_minutes.config import VadConfig
from meeting_minutes.audio.vad import SpeechSegmenter


def test_speech_segmenter_emits_speech_after_trailing_silence() -> None:
    segmenter = SpeechSegmenter(
        VadConfig(
            frame_ms=100,
            speech_threshold=0.01,
            silence_seconds=0.2,
            min_speech_seconds=0.2,
            max_speech_seconds=5,
            padding_seconds=0.1,
        ),
        sample_rate=10,
    )
    audio = np.concatenate(
        (
            np.zeros(2, dtype=np.float32),
            np.full(4, 0.1, dtype=np.float32),
            np.zeros(3, dtype=np.float32),
        )
    )

    segments = list(segmenter.process(audio))

    assert len(segments) == 1
    assert segments[0].start_seconds == 0.1
    assert segments[0].end_seconds == 0.6
    assert np.allclose(segments[0].audio, [0.0, 0.1, 0.1, 0.1, 0.1])


def test_speech_segmenter_pre_roll_excludes_trailing_silence() -> None:
    segmenter = SpeechSegmenter(
        VadConfig(
            frame_ms=100,
            speech_threshold=0.01,
            silence_seconds=0.2,
            min_speech_seconds=0.1,
            max_speech_seconds=5,
            padding_seconds=0.2,
        ),
        sample_rate=10,
    )
    audio = np.concatenate(
        (
            np.full(3, 0.1, dtype=np.float32),
            np.zeros(2, dtype=np.float32),
            np.full(2, 0.1, dtype=np.float32),
            np.zeros(2, dtype=np.float32),
        )
    )

    segments = list(segmenter.process(audio))

    assert len(segments) == 2
    assert np.allclose(segments[1].audio, [0.1, 0.1, 0.1, 0.1])


def test_speech_segmenter_forces_split_when_speech_is_too_long() -> None:
    segmenter = SpeechSegmenter(
        VadConfig(
            frame_ms=100,
            speech_threshold=0.01,
            silence_seconds=0.5,
            min_speech_seconds=0.1,
            max_speech_seconds=0.3,
            padding_seconds=0,
        ),
        sample_rate=10,
    )

    segments = list(segmenter.process(np.full(5, 0.1, dtype=np.float32)))

    assert [(segment.start_seconds, segment.end_seconds) for segment in segments] == [(0.0, 0.3)]


def test_speech_segmenter_drops_short_noise() -> None:
    segmenter = SpeechSegmenter(
        VadConfig(
            frame_ms=100,
            speech_threshold=0.01,
            silence_seconds=0.2,
            min_speech_seconds=0.5,
            max_speech_seconds=5,
            padding_seconds=0,
        ),
        sample_rate=10,
    )
    audio = np.concatenate((np.full(2, 0.1, dtype=np.float32), np.zeros(3, dtype=np.float32)))

    assert list(segmenter.process(audio)) == []


def test_speech_segmenter_carries_partial_frames_across_chunks() -> None:
    segmenter = SpeechSegmenter(
        VadConfig(
            frame_ms=100,
            speech_threshold=0.01,
            silence_seconds=0.2,
            min_speech_seconds=0.1,
            max_speech_seconds=5,
            padding_seconds=0,
        ),
        sample_rate=10,
    )

    assert list(segmenter.process(np.array([0.1], dtype=np.float32))) == []
    assert list(segmenter.process(np.array([0.1], dtype=np.float32))) == []
    segments = segmenter.flush()

    assert len(segments) == 1
    segment = segments[0]
    assert segment.start_seconds == 0
    assert segment.end_seconds == 0.2
    assert np.allclose(segment.audio, [0.1, 0.1])


def test_speech_segmenter_flush_returns_pending_segments_as_list() -> None:
    segmenter = SpeechSegmenter(
        VadConfig(
            frame_ms=200,
            speech_threshold=0.01,
            silence_seconds=0.2,
            min_speech_seconds=0.1,
            max_speech_seconds=1.0,
            padding_seconds=0,
        ),
        sample_rate=10,
    )
    assert list(segmenter.process(np.array([0.1], dtype=np.float32))) == []

    segments = segmenter.flush()

    assert [(segment.start_seconds, segment.end_seconds) for segment in segments] == [(0.0, 0.1)]


def test_speech_segmenter_passthrough_when_disabled() -> None:
    segmenter = SpeechSegmenter(VadConfig(enabled=False), sample_rate=10)

    segments = list(segmenter.process(np.arange(5, dtype=np.float32)))

    assert len(segments) == 1
    assert segments[0].start_seconds == 0
    assert segments[0].end_seconds == 0.5
    assert np.array_equal(segments[0].audio, np.arange(5, dtype=np.float32))
