from pathlib import Path
from typing import Literal

from meeting_minutes.config import AppConfig
from meeting_minutes.ollama_client import OllamaClient
from meeting_minutes.prompts import DRAFT_PROMPT, FINAL_PROMPT
from meeting_minutes.vocabulary import build_summary_section, load_vocabulary

MinutesMode = Literal["draft", "final"]


def split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
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


def generate_minutes(
    transcript_file: Path,
    mode: MinutesMode,
    output: Path | None,
    config: AppConfig,
) -> Path:
    transcript = transcript_file.read_text(encoding="utf-8")
    chunks = split_text(
        transcript,
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap,
    )
    vocabulary_section = build_summary_section(load_vocabulary(config.vocabulary))

    with OllamaClient(config.summarization) as client:
        if len(chunks) == 1:
            minutes = client.generate(_prompt_for(mode, transcript, vocabulary_section))
        else:
            summaries = [
                client.generate(_summary_prompt(index, len(chunks), chunk, vocabulary_section))
                for index, chunk in enumerate(chunks, start=1)
            ]
            integrated_source = "\n\n".join(
                f"## Chunk Summary {index}\n{summary}"
                for index, summary in enumerate(summaries, start=1)
            )
            minutes = client.generate(_prompt_for(mode, integrated_source, vocabulary_section))

    if output is None:
        output_name = "minutes_draft.md" if mode == "draft" else "minutes.md"
        output = transcript_file.parent / output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(minutes.rstrip() + "\n", encoding="utf-8")
    return output
