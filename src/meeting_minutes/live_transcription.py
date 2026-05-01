from typing import Protocol

import numpy as np

from meeting_minutes.dedupe import TranscriptDedupe
from meeting_minutes.transcribe import TranscriptionSegment
from meeting_minutes.transcript_filter import TranscriptFilter
from meeting_minutes.vad import SpeechSegment, SpeechSegmenter


class SegmentWriter(Protocol):
    def write_segments(
        self,
        segments: list[TranscriptionSegment],
        *,
        chunk_start_seconds: float,
    ) -> None: ...


class SegmentTranscriber(Protocol):
    def transcribe_segments(
        self,
        audio: np.ndarray,
        *,
        initial_prompt: str | None = None,
    ) -> list[TranscriptionSegment]: ...


class PromptContext(Protocol):
    def build(self) -> str | None: ...

    def append(self, text: str) -> None: ...


class SpeechTranscriptionRunner:
    def __init__(
        self,
        *,
        speech_segmenter: SpeechSegmenter,
        transcriber: SegmentTranscriber,
        dedupe: TranscriptDedupe,
        transcript_filter: TranscriptFilter,
        segment_writer: SegmentWriter,
        prompt_context: PromptContext | None = None,
    ) -> None:
        self._speech_segmenter = speech_segmenter
        self._transcriber = transcriber
        self._dedupe = dedupe
        self._transcript_filter = transcript_filter
        self._segment_writer = segment_writer
        self._prompt_context = prompt_context

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
        initial_prompt = self._prompt_context.build() if self._prompt_context else None
        segments = self._transcriber.transcribe_segments(
            speech_segment.audio,
            initial_prompt=initial_prompt,
        )
        text = " ".join(segment.text for segment in segments).strip()
        if not self._transcript_filter.should_keep(text):
            return False
        if not self._dedupe.should_keep(text):
            return False
        self._segment_writer.write_segments(
            segments,
            chunk_start_seconds=speech_segment.start_seconds,
        )
        if self._prompt_context:
            self._prompt_context.append(text)
        return True
