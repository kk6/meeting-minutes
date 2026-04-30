from typing import Protocol

import numpy as np

from meeting_minutes.dedupe import TranscriptDedupe
from meeting_minutes.transcribe import TranscriptionSegment
from meeting_minutes.vad import SpeechSegment, SpeechSegmenter


class SegmentWriter(Protocol):
    def write_segments(
        self,
        segments: list[TranscriptionSegment],
        *,
        chunk_start_seconds: float,
    ) -> None: ...


class SegmentTranscriber(Protocol):
    def transcribe_segments(self, audio: np.ndarray) -> list[TranscriptionSegment]: ...


class SpeechTranscriptionRunner:
    def __init__(
        self,
        *,
        speech_segmenter: SpeechSegmenter,
        transcriber: SegmentTranscriber,
        dedupe: TranscriptDedupe,
        segment_writer: SegmentWriter,
    ) -> None:
        self._speech_segmenter = speech_segmenter
        self._transcriber = transcriber
        self._dedupe = dedupe
        self._segment_writer = segment_writer

    def process(self, chunk: np.ndarray) -> bool:
        wrote_segments = False
        for speech_segment in self._speech_segmenter.process(chunk):
            wrote_segments |= self._transcribe(speech_segment)
        return wrote_segments

    def flush(self) -> bool:
        wrote_segments = False
        for speech_segment in self._speech_segmenter.flush():
            wrote_segments |= self._transcribe(speech_segment)
        return wrote_segments

    def _transcribe(self, speech_segment: SpeechSegment) -> bool:
        segments = self._transcriber.transcribe_segments(speech_segment.audio)
        text = " ".join(segment.text for segment in segments).strip()
        if not self._dedupe.should_keep(text):
            return False
        self._segment_writer.write_segments(
            segments,
            chunk_start_seconds=speech_segment.start_seconds,
        )
        return True
