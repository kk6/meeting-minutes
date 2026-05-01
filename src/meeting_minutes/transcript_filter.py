from collections import Counter
from dataclasses import dataclass, field

from meeting_minutes.config import TranscriptFilterConfig


def normalize_transcript_text(text: str) -> str:
    return " ".join(text.split())


@dataclass
class TranscriptFilterStats:
    total: int = 0
    by_reason: Counter[str] = field(default_factory=Counter)

    def record(self, reason: str) -> None:
        self.total += 1
        self.by_reason[reason] += 1

    def as_dict(self) -> dict[str, int | dict[str, int]]:
        return {
            "total": self.total,
            "by_reason": dict(sorted(self.by_reason.items())),
        }


class TranscriptFilter:
    def __init__(
        self,
        config: TranscriptFilterConfig,
        *,
        stats: TranscriptFilterStats | None = None,
    ) -> None:
        self._config = config
        self.stats = stats or TranscriptFilterStats()
        self._false_positives = {
            normalize_transcript_text(text).casefold()
            for text in config.canned_false_positives
            if normalize_transcript_text(text)
        }

    def should_keep(self, text: str) -> bool:
        normalized = normalize_transcript_text(text)
        reason = self._rejection_reason(normalized)
        if reason is None:
            return True
        self.stats.record(reason)
        return False

    def _rejection_reason(self, text: str) -> str | None:
        if not self._config.enabled:
            return None
        if not text:
            return "blank"
        if text.casefold() in self._false_positives:
            return "canned_false_positive"
        if len(text) < self._config.min_text_chars:
            return "too_short"
        if _is_repeated_short_pattern(
            text,
            max_pattern_chars=self._config.max_repeat_pattern_chars,
            min_repeats=self._config.min_repeat_count,
        ):
            return "repeated_pattern"
        return None


def _is_repeated_short_pattern(
    text: str,
    *,
    max_pattern_chars: int,
    min_repeats: int,
) -> bool:
    compact = "".join(text.split())
    if not compact or min_repeats < 2:
        return False
    max_pattern = min(max_pattern_chars, len(compact) // min_repeats)
    for pattern_length in range(1, max_pattern + 1):
        if len(compact) % pattern_length != 0:
            continue
        repeats = len(compact) // pattern_length
        if repeats < min_repeats:
            continue
        pattern = compact[:pattern_length]
        if pattern * repeats == compact:
            return True
    return False
