import numpy as np

from meeting_minutes.config import TranscriptionConfig
from meeting_minutes.errors import TranscriptionError


class WhisperTranscriber:
    def __init__(self, config: TranscriptionConfig) -> None:
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

    def transcribe(self, audio: np.ndarray) -> str:
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self._language,
                vad_filter=True,
                beam_size=1,
            )
            texts = [segment.text.strip() for segment in segments if segment.text.strip()]
        except (RuntimeError, ValueError) as exc:
            raise TranscriptionError(f"文字起こしに失敗しました: {exc}") from exc
        return " ".join(texts).strip()
