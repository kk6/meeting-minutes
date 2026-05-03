from pathlib import Path

from meeting_minutes.core.output import append_transcript_segment, format_elapsed


def test_format_elapsed_zero_pads_hms() -> None:
    assert format_elapsed(8) == "00:00:08"
    assert format_elapsed(3661) == "01:01:01"


def test_append_transcript_segment_writes_start_and_end(tmp_path: Path) -> None:
    path = tmp_path / "transcript.md"

    append_transcript_segment(path, 1, 8, "hello")

    assert path.read_text(encoding="utf-8") == "[00:00:01 - 00:00:08] hello\n"
