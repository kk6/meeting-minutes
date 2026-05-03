"""VAD・書き起こし・フィルタ・重複除去・出力の協調を担うランナー層。"""

from typing import Protocol

import numpy as np

from meeting_minutes.audio.vad import SpeechSegment, SpeechSegmenter
from meeting_minutes.transcription.dedupe import TranscriptDedupe
from meeting_minutes.transcription.filter import TranscriptFilter
from meeting_minutes.transcription.transcribe import TranscriptionSegment


class SegmentWriter(Protocol):
    """確定したセグメントを永続化するシンクの最小契約。"""

    def write_segments(
        self,
        segments: list[TranscriptionSegment],
        *,
        chunk_start_seconds: float,
    ) -> None: ...


class SegmentTranscriber(Protocol):
    """音声配列をセグメントの列に書き起こすトランスクライバーの契約。"""

    def transcribe_segments(
        self,
        audio: np.ndarray,
        *,
        initial_prompt: str | None = None,
    ) -> list[TranscriptionSegment]: ...


class PromptContext(Protocol):
    """initial_prompt を動的に構築・更新するコンテキスト保持器の契約。"""

    def build(self) -> str | None: ...

    def append(self, text: str) -> None: ...


class SpeechTranscriptionRunner:
    """発話区間ごとに「書き起こし→フィルタ→重複除去→書き出し」を実行する協調器。"""

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
