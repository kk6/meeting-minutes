from dataclasses import dataclass

import numpy as np

from meeting_minutes.config import TranscriptionConfig
from meeting_minutes.errors import TranscriptionError


@dataclass(frozen=True)
class TranscriptionSegment:
    start: float
    end: float
    text: str


class WhisperTranscriber:
    def __init__(
        self,
        config: TranscriptionConfig,
        *,
        initial_prompt: str | None = None,
    ) -> None:
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                config.whisper_model,
                device=config.device,
                compute_type=config.compute_type,
            )
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise TranscriptionError(f"Whisperモデルをロードできませんでした: {exc}") from exc
        self._language = config.language
        self._initial_prompt = initial_prompt or None

    def transcribe(self, audio: np.ndarray) -> str:
        return " ".join(segment.text for segment in self.transcribe_segments(audio)).strip()

    def transcribe_segments(self, audio: np.ndarray) -> list[TranscriptionSegment]:
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self._language,
                vad_filter=True,
                beam_size=1,
                initial_prompt=self._initial_prompt,
            )
            results = [
                TranscriptionSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=text,
                )
                for segment in segments
                if (text := segment.text.strip())
            ]
        except (RuntimeError, ValueError) as exc:
            raise TranscriptionError(f"文字起こしに失敗しました: {exc}") from exc
        return results
