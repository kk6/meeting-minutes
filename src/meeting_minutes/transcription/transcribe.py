"""faster-whisper を用いた音声書き起こしのラッパー。"""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from huggingface_hub import snapshot_download

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

            model_path = _ensure_model_available(config.whisper_model)
            self._model = WhisperModel(
                model_path,
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


def _ensure_model_available(model: str) -> str:
    """Download named Hugging Face models with progress before faster-whisper loads them."""
    if Path(model).exists():
        return model

    from faster_whisper.transcribe import download_model  # type: ignore[import-untyped]

    model_repos = _model_repos(download_model.__globals__.get("_MODELS"))
    repo_id = model if "/" in model else model_repos.get(model)
    if repo_id is None:
        raise ValueError(
            f"Invalid model size '{model}', expected one of: {', '.join(model_repos.keys())}"
        )

    return snapshot_download(
        repo_id,
        allow_patterns=[
            "config.json",
            "preprocessor_config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.*",
        ],
    )


def _model_repos(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(repo_id, str) for key, repo_id in value.items()
    ):
        raise ValueError("faster-whisper model mapping is unavailable")
    return cast(dict[str, str], value)
