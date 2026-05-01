from meeting_minutes.config import TranscriptFilterConfig
from meeting_minutes.transcript_filter import TranscriptFilter, TranscriptFilterStats


def test_transcript_filter_skips_canned_false_positive() -> None:
    stats = TranscriptFilterStats()
    transcript_filter = TranscriptFilter(
        TranscriptFilterConfig(canned_false_positives=["Thank you."]),
        stats=stats,
    )

    assert not transcript_filter.should_keep(" Thank   you. ")
    assert stats.as_dict() == {"total": 1, "by_reason": {"canned_false_positive": 1}}


def test_transcript_filter_skips_repeated_short_pattern() -> None:
    transcript_filter = TranscriptFilter(TranscriptFilterConfig())

    assert not transcript_filter.should_keep("はいはいはいはい")


def test_transcript_filter_keeps_normal_text() -> None:
    transcript_filter = TranscriptFilter(TranscriptFilterConfig())

    assert transcript_filter.should_keep("今日は仕様を確認します")
