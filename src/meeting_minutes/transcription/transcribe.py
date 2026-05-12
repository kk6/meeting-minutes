"""faster-whisper を用いた音声書き起こしのラッパー。"""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

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
    from faster_whisper.transcribe import download_model  # type: ignore[import-untyped]

    try:
        model_repos = _model_repos(download_model.__globals__.get("_MODELS"))
    except ValueError:
        model_repos = {}

    repo_id = model_repos.get(model)
    if repo_id is None and _is_path_like_model(model):
        model_path = Path(model).expanduser()
        if model_path.exists():
            return str(model_path)

    if repo_id is None:
        return model

    try:
        return _download_model_snapshot(repo_id)
    except Exception as exc:
        raise ValueError(f"Whisperモデルをダウンロードできませんでした: {exc}") from exc


def _download_model_snapshot(repo_id: str) -> str:
    return _snapshot_download(
        repo_id,
        allow_patterns=[
            "config.json",
            "preprocessor_config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.*",
        ],
    )


def _snapshot_download(repo_id: str, *, allow_patterns: list[str]) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(repo_id, allow_patterns=allow_patterns)


def _is_path_like_model(model: str) -> bool:
    return (
        model.startswith(("~", "."))
        or Path(model).is_absolute()
        or "/" in model
        or "\\" in model
    )


def _model_repos(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(repo_id, str) for key, repo_id in value.items()
    ):
        raise ValueError("faster-whisper model mapping is unavailable")
    return cast(dict[str, str], value)
