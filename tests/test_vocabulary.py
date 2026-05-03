from pathlib import Path

from meeting_minutes.config import VocabularyConfig
from meeting_minutes.core.vocabulary import (
    RecentTranscriptContext,
    Vocabulary,
    build_contextual_initial_prompt,
    build_initial_prompt,
    build_summary_section,
    load_vocabulary,
)


def test_load_vocabulary_returns_empty_when_files_unset() -> None:
    vocab = load_vocabulary(VocabularyConfig())

    assert vocab.is_empty


def test_load_vocabulary_skips_blank_and_comment_lines(tmp_path: Path) -> None:
    glossary = tmp_path / "glossary.txt"
    glossary.write_text(
        "\n# 用語集\nABCプロジェクト\n\n  XYZ製品  \n# trailing comment\n",
        encoding="utf-8",
    )

    vocab = load_vocabulary(VocabularyConfig(glossary_file=glossary))

    assert vocab.glossary == ["ABCプロジェクト", "XYZ製品"]
    assert vocab.participants == []


def test_load_vocabulary_returns_empty_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"

    vocab = load_vocabulary(VocabularyConfig(participants_file=missing))

    assert vocab.is_empty


def test_load_vocabulary_returns_empty_when_file_not_utf8(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.txt"
    bad_file.write_bytes(b"\xff\xfe\x00")  # UTF-8 として無効なバイト列

    vocab = load_vocabulary(VocabularyConfig(glossary_file=bad_file))

    assert vocab.is_empty


def test_build_initial_prompt_returns_none_for_empty_vocab() -> None:
    assert build_initial_prompt(Vocabulary(), max_chars=200) is None


def test_build_initial_prompt_combines_participants_and_glossary() -> None:
    vocab = Vocabulary(participants=["田中", "鈴木"], glossary=["ABC", "XYZ"])

    prompt = build_initial_prompt(vocab, max_chars=200)

    assert prompt == "参加者: 田中、鈴木 用語: ABC、XYZ"


def test_build_initial_prompt_truncates_at_separator_boundary() -> None:
    # "参加者: 田中、鈴木 用語: ABC、XYZ" の先頭13文字 "参加者: 田中、鈴" で切るが
    # 区切り文字「、」の手前 "参加者: 田中" で止まることを確認する。
    vocab = Vocabulary(participants=["田中", "鈴木"], glossary=["ABC", "XYZ"])

    prompt = build_initial_prompt(vocab, max_chars=9)

    assert prompt == "参加者: 田中"


def test_build_initial_prompt_returns_empty_when_no_separator_in_budget() -> None:
    vocab = Vocabulary(participants=["田中"])

    prompt = build_initial_prompt(vocab, max_chars=3)

    assert prompt == ""


def test_build_initial_prompt_returns_none_when_max_chars_zero() -> None:
    vocab = Vocabulary(participants=["田中"])

    assert build_initial_prompt(vocab, max_chars=0) is None


def test_build_contextual_initial_prompt_combines_static_and_recent_context() -> None:
    vocab = Vocabulary(participants=["田中"], glossary=["ABC"])

    prompt = build_contextual_initial_prompt(
        vocab,
        recent_context="今日は ABC の設計を確認します",
        max_chars=80,
        recent_context_chars=20,
    )

    assert prompt == "参加者: 田中 用語: ABC 直近の文字起こし: 今日は ABC の設計を確認します"


def test_build_contextual_initial_prompt_preserves_recent_context_label_when_truncated() -> None:
    prompt = build_contextual_initial_prompt(
        Vocabulary(),
        recent_context="first second third fourth",
        max_chars=20,
        recent_context_chars=100,
    )

    assert prompt == "直近の文字起こし: fourth"


def test_recent_transcript_context_keeps_recent_tail() -> None:
    context = RecentTranscriptContext(max_chars=10)

    context.append("first phrase")
    context.append("second phrase")

    assert context.text == "phrase"


def test_build_summary_section_returns_empty_for_empty_vocab() -> None:
    assert build_summary_section(Vocabulary()) == ""


def test_build_summary_section_returns_empty_when_max_chars_zero() -> None:
    assert build_summary_section(Vocabulary(participants=["田中"]), max_chars=0) == ""


def test_build_summary_section_includes_participants_and_glossary() -> None:
    vocab = Vocabulary(participants=["田中", "鈴木"], glossary=["ABC"])

    section = build_summary_section(vocab, max_chars=1000)

    assert "## 参加者" in section
    assert "- 田中" in section
    assert "- 鈴木" in section
    assert "## 用語" in section
    assert "- ABC" in section
    assert section.endswith("\n")


def test_build_summary_section_truncates_at_term_boundary() -> None:
    vocab = Vocabulary(participants=["田中", "鈴木"], glossary=["ABC", "XYZ"])

    # 田中は入るが鈴木以降は入らないよう上限を設定（田中まで57文字、鈴木追加で62文字）
    section = build_summary_section(vocab, max_chars=60)

    assert "- 田中" in section
    assert "- 鈴木" not in section
    assert len(section) <= 60


def test_build_summary_section_returns_empty_when_budget_too_small() -> None:
    vocab = Vocabulary(participants=["田中"])

    assert build_summary_section(vocab, max_chars=5) == ""
