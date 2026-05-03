import numpy as np

from meeting_minutes.config import TranscriptionConfig
from meeting_minutes.transcription.transcribe import WhisperTranscriber


class FakeWhisperSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class FakeWhisperModel:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, object] = {}

    def transcribe(
        self,
        audio: np.ndarray,
        **kwargs: object,
    ) -> tuple[list[FakeWhisperSegment], None]:
        assert audio.dtype == np.float32
        assert kwargs["language"] == "ja"
        self.last_kwargs = kwargs
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
    transcriber._initial_prompt = None

    segments = transcriber.transcribe_segments(np.zeros(16000, dtype=np.float32))

    assert [(segment.start, segment.end, segment.text) for segment in segments] == [
        (0.2, 1.0, "こんにちは"),
        (2.1, 3.0, "お願いします"),
    ]


def test_transcribe_keeps_joined_text_compatibility() -> None:
    transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
    transcriber._model = FakeWhisperModel()
    transcriber._language = TranscriptionConfig().language
    transcriber._initial_prompt = None

    text = transcriber.transcribe(np.zeros(16000, dtype=np.float32))

    assert text == "こんにちは お願いします"


def test_transcribe_segments_passes_initial_prompt() -> None:
    fake_model = FakeWhisperModel()
    transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
    transcriber._model = fake_model
    transcriber._language = "ja"
    transcriber._initial_prompt = "参加者: 田中"

    transcriber.transcribe_segments(np.zeros(16000, dtype=np.float32))

    assert fake_model.last_kwargs["initial_prompt"] == "参加者: 田中"


def test_transcribe_segments_accepts_per_call_initial_prompt() -> None:
    fake_model = FakeWhisperModel()
    transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
    transcriber._model = fake_model
    transcriber._language = "ja"
    transcriber._initial_prompt = "参加者: 田中"

    transcriber.transcribe_segments(
        np.zeros(16000, dtype=np.float32),
        initial_prompt="参加者: 鈴木",
    )

    assert fake_model.last_kwargs["initial_prompt"] == "参加者: 鈴木"
