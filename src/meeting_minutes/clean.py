"""文字起こしを LLM で整形し、Markdown として書き出すパイプライン。"""

from collections.abc import Sequence
from pathlib import Path

from meeting_minutes.config import AppConfig
from meeting_minutes.errors import MeetingMinutesError
from meeting_minutes.ollama_client import OllamaClient
from meeting_minutes.prompts import CLEAN_PROMPT
from meeting_minutes.summarize import read_transcripts, split_text


def clean_transcript(
    transcript_files: Sequence[Path],
    output: Path | None,
    config: AppConfig,
) -> Path:
    """文字起こしファイルを整形し、書き出したパスを返す。

    フィラー・言い直し・重複・句読点不足を LLM に機械的に整形させる。
    要約とは異なり原文に近い形を保つため、chunk_overlap はデフォルト 0。

    `output` が None の場合、最初のファイルと同じディレクトリに
    `cleaning.output_filename` で保存する。

    Args:
        transcript_files: 整形対象のファイルパス。複数指定時は順序通りに連結する。
        output: 出力先パス。None の場合は最初のファイルの親ディレクトリに既定名で保存。
        config: アプリ設定。

    Raises:
        MeetingMinutesError: ファイルが1つも指定されていない場合。
        OllamaError: Ollama API の呼び出しが失敗した場合。
    """
    files = list(transcript_files)
    if not files:
        raise MeetingMinutesError("文字起こしファイルを1つ以上指定してください。")

    transcript = read_transcripts(files)
    chunks = split_text(
        transcript,
        chunk_size=config.cleaning.chunk_size,
        chunk_overlap=config.cleaning.chunk_overlap,
    )

    with OllamaClient(config.summarization) as client:
        cleaned_parts = [client.generate(CLEAN_PROMPT.format(transcript=chunk)) for chunk in chunks]

    cleaned = "\n\n".join(part.strip() for part in cleaned_parts)

    output_path = (
        output if output is not None else files[0].parent / config.cleaning.output_filename
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cleaned.rstrip() + "\n", encoding="utf-8")
    return output_path
