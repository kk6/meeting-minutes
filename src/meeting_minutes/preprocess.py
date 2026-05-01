import numpy as np

from meeting_minutes.config import PreprocessingConfig


class AudioPreprocessor:
    def __init__(self, config: PreprocessingConfig) -> None:
        self._config = config

    def process(self, audio: np.ndarray) -> np.ndarray:
        processed = np.asarray(audio, dtype=np.float32)
        if not self._config.enabled:
            return processed

        if self._config.noise_gate_enabled:
            processed = self._noise_gate(processed)
        if self._config.normalize_peak:
            processed = self._normalize_peak(processed)
        return processed

    def _noise_gate(self, audio: np.ndarray) -> np.ndarray:
        if audio.size == 0:
            return audio
        threshold = np.float32(self._config.noise_gate_threshold)
        return np.where(np.abs(audio) < threshold, np.float32(0.0), audio)

    def _normalize_peak(self, audio: np.ndarray) -> np.ndarray:
        if audio.size == 0:
            return audio
        peak = np.max(np.abs(audio))
        if peak <= 0:
            return audio
        gain = np.float32(self._config.target_peak) / peak
        processed = np.empty_like(audio)
        np.multiply(audio, gain, out=processed)
        np.clip(processed, np.float32(-1.0), np.float32(1.0), out=processed)
        return processed
