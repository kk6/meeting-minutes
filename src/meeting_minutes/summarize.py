"""文字起こしから議事録 Markdown を生成するパイプライン。"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from meeting_minutes.config import AppConfig
from meeting_minutes.errors import MeetingMinutesError
from meeting_minutes.ollama_client import OllamaClient
from meeting_minutes.prompts import DRAFT_PROMPT, FINAL_PROMPT
from meeting_minutes.vocabulary import build_summary_section, load_vocabulary

MinutesMode = Literal["draft", "final"]


def split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """`text` を重なり付きで分割する。"""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def _prompt_for(mode: MinutesMode, transcript: str, vocabulary_section: str) -> str:
    template = DRAFT_PROMPT if mode == "draft" else FINAL_PROMPT
    return template.format(transcript=transcript, vocabulary_section=vocabulary_section)


def _summary_prompt(
    part_number: int,
    total_parts: int,
    transcript: str,
    vocabulary_section: str,
) -> str:
    return f"""以下は会議文字起こしの一部です。
後で全体議事録に統合できるよう、事実だけを簡潔に要約してください。

制約:
- 文字起こしにない内容を補完しない
- 決定事項、TODO、未決事項、重要な数値や日付を保持する
- 不明な内容は不明と書く

Part: {part_number}/{total_parts}

{vocabulary_section}文字起こし:
{transcript}
"""


def _generate_from_chunks(
    client: OllamaClient,
    mode: MinutesMode,
    chunks: list[str],
    vocabulary_section: str,
) -> str:
    if len(chunks) == 1:
        return client.generate(_prompt_for(mode, chunks[0], vocabulary_section))

    summaries = [
        client.generate(_summary_prompt(index, len(chunks), chunk, vocabulary_section))
        for index, chunk in enumerate(chunks, start=1)
    ]
    integrated_source = _format_chunk_summaries(summaries)
    return client.generate(_prompt_for(mode, integrated_source, vocabulary_section))


def _format_chunk_summaries(summaries: list[str]) -> str:
    return "\n\n".join(
        f"## Chunk Summary {index}\n{summary}" for index, summary in enumerate(summaries, start=1)
    )


def _default_output_path(transcript_file: Path, mode: MinutesMode) -> Path:
    output_name = "minutes_draft.md" if mode == "draft" else "minutes.md"
    return transcript_file.parent / output_name


def read_transcripts(transcript_files: Sequence[Path]) -> str:
    """文字起こしファイル群を `## Transcript N: <name>` 見出しで連結して返す。

    Args:
        transcript_files: 読み込み対象のファイルパス。順序は出力順序と一致する。

    Returns:
        全ファイルを順序通りに連結した Markdown 文字列。
    """
    sections = []
    for index, transcript_file in enumerate(transcript_files, start=1):
        transcript = transcript_file.read_text(encoding="utf-8").strip()
        sections.append(f"## Transcript {index}: {transcript_file.name}\n\n{transcript}")
    return "\n\n".join(sections)


def generate_minutes(
    transcript_file: Path | Sequence[Path],
    mode: MinutesMode,
    output: Path | None,
    config: AppConfig,
) -> Path:
    """文字起こしファイルから議事録 Markdown を生成し、書き出したパスを返す。

    `output` が None の場合、最初の文字起こしファイルと同じディレクトリに既定名で保存する。
    入力ファイルの読み込み失敗（`OSError` / `UnicodeError`）や、`MeetingMinutesError`
    系（入力不正、Ollama 失敗）の例外を送出する。
    """
    transcript_files = (
        [transcript_file] if isinstance(transcript_file, Path) else list(transcript_file)
    )
    if not transcript_files:
        raise MeetingMinutesError("文字起こしファイルを1つ以上指定してください。")

    transcript = read_transcripts(transcript_files)
    chunks = split_text(
        transcript,
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap,
    )
    vocabulary_section = build_summary_section(
        load_vocabulary(config.vocabulary),
        max_chars=config.vocabulary.max_summary_chars,
    )

    with OllamaClient(config.summarization) as client:
        minutes = _generate_from_chunks(client, mode, chunks, vocabulary_section)

    if output is None:
        output = _default_output_path(transcript_files[0], mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(minutes.rstrip() + "\n", encoding="utf-8")
    return output
