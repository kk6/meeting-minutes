"""faster-whisper を用いた音声書き起こしのラッパー。"""

from dataclasses import dataclass

import numpy as np

from meeting_minutes.config import TranscriptionConfig
from meeting_minutes.errors import TranscriptionError


@dataclass(frozen=True)
class TranscriptionSegment:
    """Whisper が出力した 1 セグメント分の時刻付きテキスト。"""

    start: float
    end: float
    text: str


class WhisperTranscriber:
    """faster-whisper モデルをロードして音声を書き起こす同期トランスクライバー。"""

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

    def transcribe(self, audio: np.ndarray, *, initial_prompt: str | None = None) -> str:
        return " ".join(
            segment.text
            for segment in self.transcribe_segments(
                audio,
                initial_prompt=initial_prompt,
            )
        ).strip()

    def transcribe_segments(
        self,
        audio: np.ndarray,
        *,
        initial_prompt: str | None = None,
    ) -> list[TranscriptionSegment]:
        prompt = initial_prompt if initial_prompt is not None else self._initial_prompt
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self._language,
                vad_filter=True,
                beam_size=1,
                initial_prompt=prompt,
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
