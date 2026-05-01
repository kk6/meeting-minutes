"""`meeting-minutes doctor` 用に外部依存（ffmpeg, 音声入力, Ollama, Whisper）の疎通確認を行う。"""

import logging
import shutil

import httpx
import sounddevice as sd

from meeting_minutes.config import AppConfig
from meeting_minutes.devices import list_input_devices

logger = logging.getLogger(__name__)


def run_checks(config: AppConfig) -> list[tuple[str, bool, str]]:
    """各種依存の疎通結果を `(項目名, 成功フラグ, 詳細)` のリストで返す。"""
    results: list[tuple[str, bool, str]] = []

    ffmpeg = shutil.which("ffmpeg")
    results.append(("ffmpeg", ffmpeg is not None, ffmpeg or "not found"))

    try:
        devices = list_input_devices()
        blackhole = any(device.is_blackhole for device in devices)
        message = f"{len(devices)} input device(s)"
        if blackhole:
            message += ", BlackHole detected"
        results.append(("sounddevice inputs", True, message))
    except (OSError, sd.PortAudioError) as exc:  # pragma: no cover - depends on host audio stack
        logger.exception("Audio input check failed")
        results.append(("sounddevice inputs", False, str(exc)))

    base_url = config.summarization.ollama_base_url.rstrip("/")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        model_names = {model.get("name", "") for model in models}
        wanted = config.summarization.ollama_model
        found = any(name == wanted or name.startswith(f"{wanted}:") for name in model_names)
        results.append(("Ollama API", True, f"{base_url} reachable"))
        results.append((f"Ollama model {wanted}", found, "available" if found else "not found"))
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("Ollama API check failed")
        results.append(("Ollama API", False, str(exc)))
        results.append((f"Ollama model {config.summarization.ollama_model}", False, "not checked"))

    try:
        from faster_whisper import WhisperModel  # noqa: F401

        results.append(("faster-whisper", True, "import ok"))
    except ImportError as exc:  # pragma: no cover - depends on optional import
        logger.exception("faster-whisper import check failed")
        results.append(("faster-whisper", False, str(exc)))

    return results
