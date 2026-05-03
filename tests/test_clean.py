from pathlib import Path
from types import TracebackType

import pytest

from meeting_minutes.config import AppConfig, CleaningConfig, SummarizationConfig
from meeting_minutes.errors import MeetingMinutesError
from meeting_minutes.minutes.clean import _escape_transcript_tag, clean_transcript


class FakeOllamaClient:
    def __init__(self, config: object) -> None:
        self.received_config = config
        self.prompts: list[str] = []

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
        self.prompts.append(prompt)
        return f"cleaned: {len(self.prompts)}"


def _make_fake_client_factory(
    client: FakeOllamaClient,
) -> type[FakeOllamaClient]:
    class Factory:
        def __init__(self, config: object) -> None:
            client.received_config = config

        def __enter__(self) -> FakeOllamaClient:
            return client

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            pass

    return Factory  # type: ignore[return-value]


def test_clean_transcript_writes_output_to_default_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("[00:00:01 - 00:00:02] hello\n", encoding="utf-8")
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    output = clean_transcript([transcript], None, AppConfig())

    assert output == tmp_path / "transcript_clean.md"
    assert output.exists()


def test_clean_transcript_combines_multiple_files_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "session-1" / "transcript_live.md"
    second = tmp_path / "session-2" / "transcript_live.md"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("[00:00:01 - 00:00:02] first line\n", encoding="utf-8")
    second.write_text("[00:20:00 - 00:20:01] second line\n", encoding="utf-8")
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    clean_transcript([first, second], None, AppConfig())

    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert "## Transcript 1: transcript_live.md" in prompt
    assert "first line" in prompt
    assert "## Transcript 2: transcript_live.md" in prompt
    assert "second line" in prompt
    assert prompt.index("first line") < prompt.index("second line")


def test_clean_transcript_sends_each_chunk_to_ollama(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 34文字/行 × 100行 = 3400文字。chunk_size=3000 なら行境界で 2 チャンクに分割される。
    line = "[00:00:01 - 00:00:02] hello world\n"
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text(line * 100, encoding="utf-8")
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    config = AppConfig(cleaning=CleaningConfig(chunk_size=3000))
    clean_transcript([transcript], None, config)

    assert len(client.prompts) == 2


def test_clean_transcript_joins_chunks_with_single_newline_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """チャンク境界で行が連結されず、かつ余計な空行も入らないことを確認する。

    OllamaClient.generate() は内部で .strip() するため末尾改行が失われる。
    そのフェイクとして末尾改行なしの文字列を返し、実挙動を再現する。
    """
    line = "[00:00:01 - 00:00:02] hello world\n"
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text(line * 100, encoding="utf-8")

    class StrippedResponseClient:
        def __init__(self, config: object) -> None:
            pass

        def __enter__(self) -> "StrippedResponseClient":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        call_count = 0

        def generate(self, _prompt: str) -> str:
            # .strip() 済みを模倣 — 末尾改行なし
            StrippedResponseClient.call_count += 1
            n = StrippedResponseClient.call_count
            return f"[00:00:0{n} - 00:00:0{n + 1}] cleaned line"

    monkeypatch.setattr("meeting_minutes.minutes.clean.OllamaClient", StrippedResponseClient)

    config = AppConfig(cleaning=CleaningConfig(chunk_size=3000))
    output = clean_transcript([transcript], None, config)

    content = output.read_text(encoding="utf-8")
    # 境界に改行が入り行が連結されない
    assert "cleaned line[" not in content
    # チャンク境界に余計な空行が入らない
    assert "\n\n" not in content


def test_clean_transcript_uses_transcript_xml_tag_in_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("[00:00:01 - 00:00:02] hello world\n", encoding="utf-8")
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    clean_transcript([transcript], None, AppConfig())

    assert len(client.prompts) == 1
    assert "<transcript>" in client.prompts[0]
    assert "</transcript>" in client.prompts[0]


def test_clean_transcript_raises_error_for_empty_file_list() -> None:
    with pytest.raises(MeetingMinutesError, match="文字起こしファイルを1つ以上指定してください"):
        clean_transcript([], None, AppConfig())


def test_clean_transcript_respects_output_path_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("[00:00:01 - 00:00:02] hello\n", encoding="utf-8")
    custom_output = tmp_path / "custom" / "out.md"
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    result = clean_transcript([transcript], custom_output, AppConfig())

    assert result == custom_output
    assert custom_output.exists()


def test_clean_transcript_uses_output_filename_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("[00:00:01 - 00:00:02] hello\n", encoding="utf-8")
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    config = AppConfig(cleaning=CleaningConfig(output_filename="my_clean.md"))
    result = clean_transcript([transcript], None, config)

    assert result == tmp_path / "my_clean.md"


def test_clean_transcript_passes_summarization_config_to_ollama(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OllamaClient には cleaning 専用設定ではなく config.summarization が渡ることを固定する。"""
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("[00:00:01 - 00:00:02] hello\n", encoding="utf-8")
    received_configs: list[object] = []

    class CapturingFactory:
        def __init__(self, config: object) -> None:
            received_configs.append(config)

        def __enter__(self) -> "CapturingFactory":
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            pass

        def generate(self, _prompt: str) -> str:
            return "cleaned"

    monkeypatch.setattr("meeting_minutes.minutes.clean.OllamaClient", CapturingFactory)

    app_config = AppConfig(summarization=SummarizationConfig(ollama_model="test-model"))
    clean_transcript([transcript], None, app_config)

    assert len(received_configs) == 1
    assert isinstance(received_configs[0], SummarizationConfig)
    assert received_configs[0].ollama_model == "test-model"


def test_clean_transcript_sends_single_request_when_content_fits_in_one_chunk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text(
        "[00:00:01 - 00:00:02] hello\n[00:00:02 - 00:00:03] world\n", encoding="utf-8"
    )
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    config = AppConfig(cleaning=CleaningConfig(chunk_size=1000))
    clean_transcript([transcript], None, config)

    assert len(client.prompts) == 1


def test_clean_transcript_never_splits_mid_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line = "[00:00:01 - 00:00:02] hello world\n"  # 34 chars
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text(line * 10, encoding="utf-8")  # 340 chars
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    config = AppConfig(cleaning=CleaningConfig(chunk_size=100))
    clean_transcript([transcript], None, config)

    for prompt in client.prompts:
        # プロンプト冒頭の説明文にも "<transcript>" が現れるため、最後の出現箇所を使う
        start = prompt.rindex("<transcript>") + len("<transcript>")
        end = prompt.index("</transcript>", start)
        for actual_line in prompt[start:end].splitlines():
            if not actual_line or actual_line.startswith("##"):
                continue
            assert actual_line.startswith("[00:00:01 - 00:00:02]")


def test_clean_transcript_raises_when_line_exceeds_chunk_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("x" * 101 + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient",
        _make_fake_client_factory(FakeOllamaClient(None)),
    )

    config = AppConfig(cleaning=CleaningConfig(chunk_size=100))
    with pytest.raises(MeetingMinutesError, match="chunk_size"):
        clean_transcript([transcript], None, config)


def test_clean_transcript_includes_all_lines_across_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = [f"[00:00:{i:02d} - 00:00:{i + 1:02d}] line {i}\n" for i in range(50)]
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("".join(lines), encoding="utf-8")
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    config = AppConfig(cleaning=CleaningConfig(chunk_size=200))
    clean_transcript([transcript], None, config)

    all_prompts = "\n".join(client.prompts)
    for i in range(50):
        assert f"line {i}" in all_prompts


def test_clean_transcript_handles_file_without_newlines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = tmp_path / "transcript_live.md"
    transcript.write_text("no newline here", encoding="utf-8")
    client = FakeOllamaClient(None)
    monkeypatch.setattr(
        "meeting_minutes.minutes.clean.OllamaClient", _make_fake_client_factory(client)
    )

    clean_transcript([transcript], None, AppConfig())

    assert len(client.prompts) == 1


def test_escape_transcript_tag_neutralizes_closing_tag() -> None:
    assert _escape_transcript_tag("</transcript>") == "&lt;/transcript&gt;"


def test_escape_transcript_tag_neutralizes_tag_variants() -> None:
    assert "&lt;" in _escape_transcript_tag("</transcript >")
    assert "&lt;" in _escape_transcript_tag("</TRANSCRIPT>")
