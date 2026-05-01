from collections import deque
from difflib import SequenceMatcher

from meeting_minutes.transcript_filter import TranscriptFilterStats, normalize_transcript_text


class TranscriptDedupe:
    def __init__(
        self,
        similarity_threshold: float = 0.92,
        max_seen: int = 300,
        *,
        stats: TranscriptFilterStats | None = None,
    ) -> None:
        if max_seen < 1:
            raise ValueError("max_seen must be greater than or equal to 1")
        self._seen: set[str] = set()
        self._history: deque[str] = deque()
        self._last_text = ""
        self._similarity_threshold = similarity_threshold
        self._max_seen = max_seen
        self._stats = stats

    def should_keep(self, text: str) -> bool:
        normalized = normalize_transcript_text(text)
        if not normalized:
            self._record("blank")
            return False
        if normalized in self._seen:
            self._record("duplicate")
            return False
        if self._last_text:
            ratio = SequenceMatcher(None, self._last_text, normalized).ratio()
            if ratio >= self._similarity_threshold:
                self._record("similar_duplicate")
                return False
        self._remember(normalized)
        self._last_text = normalized
        return True

    def _remember(self, text: str) -> None:
        self._seen.add(text)
        self._history.append(text)
        while len(self._history) > self._max_seen:
            self._seen.remove(self._history.popleft())

    def _record(self, reason: str) -> None:
        if self._stats is not None:
            self._stats.record(reason)
