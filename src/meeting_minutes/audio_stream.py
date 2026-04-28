from collections.abc import Iterator
from queue import Full, Queue

import numpy as np
import sounddevice as sd

from meeting_minutes.errors import MeetingMinutesError


class AudioOverflowError(MeetingMinutesError):
    """Raised when transcription is too slow and the in-memory audio queue fills up."""


def audio_chunks(
    *,
    device_index: int,
    sample_rate: int,
    channels: int,
    chunk_seconds: int,
) -> Iterator[np.ndarray]:
    frames_per_chunk = sample_rate * chunk_seconds
    block_frames = max(sample_rate // 2, 1)
    queue: Queue[np.ndarray] = Queue(maxsize=240)  # 120 seconds at the current ~0.5s block size.
    dropped_blocks = 0

    def callback(
        indata: np.ndarray,
        _frames: int,
        _time: object,
        status: sd.CallbackFlags,
    ) -> None:
        nonlocal dropped_blocks
        if status.input_overflow:
            dropped_blocks += 1
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata
        try:
            queue.put_nowait(np.asarray(mono, dtype=np.float32).copy())
        except Full:
            dropped_blocks += 1

    with sd.InputStream(
        samplerate=sample_rate,
        device=device_index,
        channels=channels,
        dtype="float32",
        blocksize=block_frames,
        callback=callback,
    ):
        pending = np.empty(0, dtype=np.float32)
        while True:
            if dropped_blocks:
                dropped = dropped_blocks
                dropped_blocks = 0
                raise AudioOverflowError(
                    f"音声入力の処理が追いつかず、{dropped} block(s) を取り逃がしました。"
                )
            while pending.shape[0] < frames_per_chunk:
                pending = np.concatenate((pending, queue.get()))
            chunk = pending[:frames_per_chunk]
            pending = pending[frames_per_chunk:]
            yield chunk
