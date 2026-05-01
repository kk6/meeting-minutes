"""RMS ベースの簡易 VAD で音声チャンクを発話区間に分割する。"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from math import ceil

import numpy as np

from meeting_minutes.config import VadConfig


@dataclass(frozen=True)
class SpeechSegment:
    """発話区間として切り出された音声と、そのチャンク先頭からの時刻範囲。"""

    audio: np.ndarray
    start_seconds: float
    end_seconds: float


class SpeechSegmenter:
    """RMS 閾値で発話区間を切り出すストリーミング VAD。"""

    def __init__(self, config: VadConfig, *, sample_rate: int) -> None:
        self._config = config
        self._sample_rate = sample_rate
        self._frame_samples = max(ceil(sample_rate * config.frame_ms / 1000), 1)
        self._silence_frames = max(
            ceil(config.silence_seconds * sample_rate / self._frame_samples),
            1,
        )
        self._padding_samples = ceil(config.padding_seconds * sample_rate)
        self._min_speech_samples = ceil(config.min_speech_seconds * sample_rate)
        self._max_speech_samples = ceil(config.max_speech_seconds * sample_rate)
        self._pre_roll = np.empty(0, dtype=np.float32)
        self._pending_frame = np.empty(0, dtype=np.float32)
        self._speech_frames: list[np.ndarray] = []
        self._speech_start_sample: int | None = None
        self._silence_samples = 0
        self._silence_frame_count = 0
        self._speech_samples = 0
        self._processed_samples = 0

    def process(self, chunk: np.ndarray) -> Iterator[SpeechSegment]:
        if not self._config.enabled:
            start = self._processed_samples / self._sample_rate
            self._processed_samples += chunk.shape[0]
            yield SpeechSegment(
                audio=np.asarray(chunk, dtype=np.float32),
                start_seconds=start,
                end_seconds=self._processed_samples / self._sample_rate,
            )
            return

        mono = np.concatenate((self._pending_frame, np.asarray(chunk, dtype=np.float32)))
        frame_count = mono.shape[0] // self._frame_samples
        for index in range(frame_count):
            start = index * self._frame_samples
            frame = mono[start : start + self._frame_samples]
            yield from self._process_frame(frame)

        self._pending_frame = mono[frame_count * self._frame_samples :]

    def flush(self) -> list[SpeechSegment]:
        segments: list[SpeechSegment] = []
        if self._pending_frame.size:
            segments.extend(self._process_frame(self._pending_frame))
            self._pending_frame = np.empty(0, dtype=np.float32)
        if self._speech_start_sample is not None:
            segment = self._finish_speech(include_trailing_silence=True)
            if segment is not None:
                segments.append(segment)
        return segments

    def _process_frame(self, frame: np.ndarray) -> Iterable[SpeechSegment]:
        is_speech = float(np.sqrt(np.mean(np.square(frame)))) >= self._config.speech_threshold
        if self._speech_start_sample is None:
            if is_speech:
                self._start_speech(frame)
            else:
                self._append_pre_roll(frame)
            self._processed_samples += frame.shape[0]
            return []

        self._speech_frames.append(frame)
        self._speech_samples += frame.shape[0]
        if is_speech:
            self._silence_samples = 0
            self._silence_frame_count = 0
        else:
            self._silence_samples += frame.shape[0]
            self._silence_frame_count += 1

        self._processed_samples += frame.shape[0]
        if self._speech_samples >= self._max_speech_samples:
            segment = self._finish_speech(include_trailing_silence=True)
            return [segment] if segment is not None else []
        if self._silence_frame_count >= self._silence_frames:
            segment = self._finish_speech(include_trailing_silence=False)
            return [segment] if segment is not None else []
        return []

    def _start_speech(self, frame: np.ndarray) -> None:
        self._speech_start_sample = self._processed_samples - self._pre_roll.shape[0]
        self._speech_frames = [self._pre_roll, frame] if self._pre_roll.size else [frame]
        self._speech_samples = self._pre_roll.shape[0] + frame.shape[0]
        self._pre_roll = np.empty(0, dtype=np.float32)
        self._silence_samples = 0
        self._silence_frame_count = 0

    def _finish_speech(self, *, include_trailing_silence: bool) -> SpeechSegment | None:
        if self._speech_start_sample is None:
            return None

        speech_audio = (
            np.concatenate(self._speech_frames)
            if self._speech_frames
            else np.empty(0, dtype=np.float32)
        )
        trailing_silence_samples = 0 if include_trailing_silence else self._silence_samples
        if trailing_silence_samples:
            speech_audio = speech_audio[: speech_audio.shape[0] - trailing_silence_samples]
        speech_start_sample = self._speech_start_sample
        speech_end_sample = speech_start_sample + speech_audio.shape[0]
        self._pre_roll = (
            speech_audio[-self._padding_samples :]
            if self._padding_samples
            else np.empty(0, dtype=np.float32)
        )
        self._speech_frames = []
        self._speech_start_sample = None
        self._silence_samples = 0
        self._silence_frame_count = 0
        self._speech_samples = 0

        if speech_audio.shape[0] < self._min_speech_samples:
            return None
        return SpeechSegment(
            audio=speech_audio,
            start_seconds=speech_start_sample / self._sample_rate,
            end_seconds=speech_end_sample / self._sample_rate,
        )

    def _append_pre_roll(self, audio: np.ndarray) -> None:
        if self._padding_samples == 0:
            return
        self._pre_roll = np.concatenate((self._pre_roll, audio))[-self._padding_samples :]
