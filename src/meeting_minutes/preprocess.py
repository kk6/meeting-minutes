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
        return np.where(np.abs(audio) < self._config.noise_gate_threshold, 0.0, audio).astype(
            np.float32,
            copy=False,
        )

    def _normalize_peak(self, audio: np.ndarray) -> np.ndarray:
        if audio.size == 0:
            return audio
        peak = float(np.max(np.abs(audio)))
        if peak <= 0:
            return audio
        gain = self._config.target_peak / peak
        return np.clip(audio * gain, -1.0, 1.0).astype(np.float32, copy=False)
