import pytest

from meeting_minutes.dedupe import TranscriptDedupe


def test_dedupe_skips_exact_duplicates() -> None:
    dedupe = TranscriptDedupe()

    assert dedupe.should_keep("今日は仕様を確認します")
    assert not dedupe.should_keep("今日は仕様を確認します")


def test_dedupe_skips_blank() -> None:
    assert not TranscriptDedupe().should_keep("   ")


def test_dedupe_skips_similar_text() -> None:
    dedupe = TranscriptDedupe(similarity_threshold=0.5)

    assert dedupe.should_keep("今日は仕様を確認します")
    assert not dedupe.should_keep("今日は仕様を確認します。")


def test_dedupe_forgets_old_exact_duplicates() -> None:
    dedupe = TranscriptDedupe(max_seen=1)

    assert dedupe.should_keep("最初の発言")
    assert dedupe.should_keep("次の発言")
    assert dedupe.should_keep("最初の発言")


def test_dedupe_rejects_invalid_max_seen() -> None:
    with pytest.raises(ValueError, match="max_seen"):
        TranscriptDedupe(max_seen=0)
