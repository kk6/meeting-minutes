"""録音音声を 16bit PCM の WAV ファイルとして書き出すユーティリティ。"""

import wave
from pathlib import Path

import numpy as np


class WavAudioWriter:
    """float32 の音声サンプルを 16bit PCM WAV に逐次追記するライター。"""

    def __init__(self, path: Path, *, sample_rate: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        audio_file = wave.open(str(path), "wb")  # noqa: SIM115
        try:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(sample_rate)
        except Exception:
            audio_file.close()
            raise
        self._file = audio_file

    def write(self, audio: np.ndarray) -> None:
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype("<i2", copy=False)
        self._file.writeframes(pcm.tobytes())

    def close(self) -> None:
        self._file.close()
