import numpy as np

from meeting_minutes.config import TranscriptionConfig
from meeting_minutes.transcribe import WhisperTranscriber


class FakeWhisperSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class FakeWhisperModel:
    def transcribe(
        self,
        audio: np.ndarray,
        **kwargs: object,
    ) -> tuple[list[FakeWhisperSegment], None]:
        assert audio.dtype == np.float32
        assert kwargs["language"] == "ja"
        return (
            [
                FakeWhisperSegment(0.2, 1.0, " こんにちは "),
                FakeWhisperSegment(1.4, 2.0, ""),
                FakeWhisperSegment(2.1, 3.0, "お願いします"),
            ],
            None,
        )


def test_transcribe_segments_preserves_segment_times() -> None:
    transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
    transcriber._model = FakeWhisperModel()
    transcriber._language = "ja"

    segments = transcriber.transcribe_segments(np.zeros(16000, dtype=np.float32))

    assert [(segment.start, segment.end, segment.text) for segment in segments] == [
        (0.2, 1.0, "こんにちは"),
        (2.1, 3.0, "お願いします"),
    ]


def test_transcribe_keeps_joined_text_compatibility() -> None:
    transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
    transcriber._model = FakeWhisperModel()
    transcriber._language = TranscriptionConfig().language

    text = transcriber.transcribe(np.zeros(16000, dtype=np.float32))

    assert text == "こんにちは お願いします"
