from difflib import SequenceMatcher


class TranscriptDedupe:
    def __init__(self, similarity_threshold: float = 0.92) -> None:
        self._seen: set[str] = set()
        self._last_text = ""
        self._similarity_threshold = similarity_threshold

    def should_keep(self, text: str) -> bool:
        normalized = " ".join(text.split())
        if not normalized:
            return False
        if normalized in self._seen:
            return False
        if self._last_text:
            ratio = SequenceMatcher(None, self._last_text, normalized).ratio()
            if ratio >= self._similarity_threshold:
                return False
        self._seen.add(normalized)
        self._last_text = normalized
        return True
