"""文字起こしを LLM で整形し、Markdown として書き出すパイプライン。"""

from collections.abc import Sequence
from pathlib import Path

from meeting_minutes.config import AppConfig
from meeting_minutes.errors import MeetingMinutesError
from meeting_minutes.ollama_client import OllamaClient
from meeting_minutes.prompts import CLEAN_PROMPT
from meeting_minutes.summarize import read_transcripts


def _escape_transcript_tag(text: str) -> str:
    # < > をエンティティ化してプロンプトの <transcript> タグ境界を保護する。
    # html.escape() は & も変換するため文字起こし内の & が化ける。< > のみを対象にする。
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _split_lines(text: str, chunk_size: int) -> list[str]:
    # 行境界で分割する。文字数境界で切ると行途中でタイムスタンプ行が分断され、
    # モデルがタイムスタンプを失ったまま段落化するため。
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for lineno, line in enumerate(lines, start=1):
        if len(line) > chunk_size:
            preview = line[:40].rstrip()
            raise MeetingMinutesError(
                f"{lineno} 行目が chunk_size ({chunk_size} 文字) を超えています"
                f" ({len(line)} 文字): {preview!r} ..."
                " cleaning.chunk_size を大きくしてください。"
            )
        if current and current_len + len(line) > chunk_size:
            chunks.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


def clean_transcript(
    transcript_files: Sequence[Path],
    output: Path | None,
    config: AppConfig,
) -> Path:
    """文字起こしファイルを整形し、書き出したパスを返す。

    フィラー・言い直し・重複・句読点不足を LLM に機械的に整形させる。
    行境界で分割するため、1行が cleaning.chunk_size を超える場合はエラーになる。

    `output` が None の場合、最初のファイルと同じディレクトリに
    `cleaning.output_filename` で保存する。

    Args:
        transcript_files: 整形対象のファイルパス。複数指定時は順序通りに連結する。
        output: 出力先パス。None の場合は最初のファイルの親ディレクトリに既定名で保存。
        config: アプリ設定。

    Raises:
        MeetingMinutesError: ファイルが1つも指定されていない場合、または1行が chunk_size を超える場合。
        OllamaError: Ollama API の呼び出しが失敗した場合。
        OSError: ファイルの読み込みに失敗した場合。
        UnicodeDecodeError: ファイルが UTF-8 でデコードできない場合。
    """
    files = list(transcript_files)
    if not files:
        raise MeetingMinutesError("文字起こしファイルを1つ以上指定してください。")

    transcript = read_transcripts(files)
    chunks = _split_lines(transcript, config.cleaning.chunk_size)

    with OllamaClient(config.summarization) as client:
        cleaned_parts = [
            client.generate(CLEAN_PROMPT.format(transcript=_escape_transcript_tag(chunk)))
            for chunk in chunks
        ]

    # generate() は内部で .strip() するため末尾改行が失われる。
    # removesuffix("\n") で末尾の改行を1つだけ除去してから "\n" で結合し、
    # チャンク境界で行が連結しないようにする。rstrip だとモデルが返した末尾空行も消えるため使わない。
    cleaned = "\n".join(part.removesuffix("\n") for part in cleaned_parts)

    output_path = (
        output if output is not None else files[0].parent / config.cleaning.output_filename
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cleaned.rstrip() + "\n", encoding="utf-8")
    return output_path
