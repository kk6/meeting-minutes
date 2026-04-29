import logging
from dataclasses import dataclass, field
from pathlib import Path

from meeting_minutes.config import VocabularyConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Vocabulary:
    participants: list[str] = field(default_factory=list)
    glossary: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.participants and not self.glossary


def _read_terms(path: Path | None) -> list[str]:
    if path is None:
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("語彙ファイルが見つかりません: %s（スキップします）", path)
        return []
    except OSError as exc:
        logger.warning("語彙ファイルを読み込めませんでした: %s (%s)", path, exc)
        return []

    terms: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        terms.append(stripped)
    return terms


def load_vocabulary(config: VocabularyConfig) -> Vocabulary:
    return Vocabulary(
        participants=_read_terms(config.participants_file),
        glossary=_read_terms(config.glossary_file),
    )


def build_initial_prompt(vocab: Vocabulary, *, max_chars: int) -> str | None:
    """Whisper の initial_prompt 用ヒントを生成する。max_chars 超過分は末尾から切り詰める。"""
    if vocab.is_empty or max_chars <= 0:
        return None

    sections: list[str] = []
    if vocab.participants:
        sections.append("参加者: " + "、".join(vocab.participants))
    if vocab.glossary:
        sections.append("用語: " + "、".join(vocab.glossary))
    prompt = " ".join(sections)
    if len(prompt) <= max_chars:
        return prompt
    # Whisper のヒントは前方ほど強く効くため、末尾を落とす。
    # 単語の途中で切らないよう、区切り文字（読点・空白）の手前で止める。
    candidate = prompt[:max_chars]
    for i in range(len(candidate) - 1, -1, -1):
        if candidate[i] in ("、", " "):
            return candidate[:i]
    return ""


def build_summary_section(vocab: Vocabulary, *, max_chars: int = 0) -> str:
    """要約プロンプトに差し込む参加者・用語セクションを生成する。

    max_chars > 0 の場合、超過しないよう項目単位で末尾から切り落とす。
    空または上限 0 なら空文字列を返す。
    """
    if vocab.is_empty or max_chars == 0:
        return ""

    header = (
        "以下は今回の会議で想定される参加者・用語の一覧です。\n表記の正規化に活用してください。"
    )
    all_terms: list[tuple[str, str]] = [("参加者", name) for name in vocab.participants] + [
        ("用語", term) for term in vocab.glossary
    ]

    # 上限に収まる範囲で項目を前から詰める。
    included: list[tuple[str, str]] = []
    for section, term in all_terms:
        candidate = _build_section_text(header, included + [(section, term)])
        if len(candidate) > max_chars:
            break
        included.append((section, term))

    if not included:
        return ""
    return _build_section_text(header, included)


def _build_section_text(header: str, terms: list[tuple[str, str]]) -> str:
    parts = [header]
    current_section = ""
    for section, term in terms:
        if section != current_section:
            parts.append(f"\n## {section}")
            current_section = section
        parts.append(f"- {term}")
    return "\n".join(parts) + "\n"
