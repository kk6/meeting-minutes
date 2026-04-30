from pathlib import Path
from types import TracebackType

import pytest

from meeting_minutes.config import AppConfig
from meeting_minutes.errors import MeetingMinutesError
from meeting_minutes.summarize import generate_minutes, split_text


def test_split_text_uses_overlap() -> None:
    chunks = split_text("abcdefghij", chunk_size=4, chunk_overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]


def test_generate_minutes_combines_multiple_transcripts_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "session-1" / "transcript_live.md"
    second = tmp_path / "session-2" / "transcript_live.md"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("[00:00:01] first transcript\n", encoding="utf-8")
    second.write_text("[00:20:00] second transcript\n", encoding="utf-8")
    prompts: list[str] = []

    class FakeOllamaClient:
        def __init__(self, _config: object) -> None:
            pass

        def __enter__(self) -> "FakeOllamaClient":
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            pass

        def generate(self, prompt: str) -> str:
            prompts.append(prompt)
            return "generated minutes"

    monkeypatch.setattr("meeting_minutes.summarize.OllamaClient", FakeOllamaClient)

    output = generate_minutes([first, second], "final", None, AppConfig())

    assert output == first.parent / "minutes.md"
    assert output.read_text(encoding="utf-8") == "generated minutes\n"
    assert "## Transcript 1: transcript_live.md" in prompts[0]
    assert str(first.parent) not in prompts[0]
    assert "first transcript" in prompts[0]
    assert "## Transcript 2: transcript_live.md" in prompts[0]
    assert str(second.parent) not in prompts[0]
    assert "second transcript" in prompts[0]
    assert prompts[0].index("first transcript") < prompts[0].index("second transcript")


def test_generate_minutes_raises_domain_error_for_empty_transcripts() -> None:
    with pytest.raises(MeetingMinutesError, match="文字起こしファイルを1つ以上指定してください"):
        generate_minutes([], "final", None, AppConfig())
