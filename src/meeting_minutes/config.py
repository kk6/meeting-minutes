from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioConfig(BaseModel):
    device: str | None = None
    device_index: int | None = None
    sample_rate: int = 16_000
    channels: int = 1
    chunk_seconds: int = Field(default=8, ge=1)


class TranscriptionConfig(BaseModel):
    whisper_model: str = "small"
    language: str = "ja"
    device: str = "cpu"
    compute_type: str = "int8"


class SummarizationConfig(BaseModel):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4"
    temperature: float = 0.2
    num_ctx: int = 8192
    timeout_seconds: float = 600


class OutputConfig(BaseModel):
    base_dir: Path = Path("output")
    save_transcript: bool = True
    save_audio: bool = True


class ChunkingConfig(BaseModel):
    chunk_size: int = 6000
    chunk_overlap: int = 500


class VocabularyConfig(BaseModel):
    glossary_file: Path | None = None
    participants_file: Path | None = None
    # Whisper の initial_prompt は約 224 token が上限。日本語では 1 文字 ≒ 1〜2 token のため、
    # 200 文字を安全側のデフォルトとする。
    max_prompt_chars: int = Field(default=200, ge=0)
    # 要約プロンプトへの語彙注入上限。Ollama の num_ctx を圧迫しないよう項目単位で切り落とす。
    # 0 で語彙セクションを無効化する。
    max_summary_chars: int = Field(default=1000, ge=0)


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEETING_MINUTES_", env_nested_delimiter="__")

    audio: AudioConfig = Field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    summarization: SummarizationConfig = Field(default_factory=SummarizationConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    vocabulary: VocabularyConfig = Field(default_factory=VocabularyConfig)


def load_config(path: Path | None) -> AppConfig:
    if path is None:
        return AppConfig()
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")

    import tomllib

    with path.open("rb") as file:
        data = tomllib.load(file)
    return AppConfig.model_validate(data)


def apply_overrides(config: AppConfig, overrides: dict[str, object]) -> AppConfig:
    allowed_sections = {
        "audio",
        "transcription",
        "summarization",
        "output",
        "chunking",
        "vocabulary",
    }
    section_updates: dict[str, dict[str, object]] = {}
    for dotted_key, value in overrides.items():
        if value is None:
            continue
        if "." not in dotted_key:
            raise ValueError(
                f"Invalid override key '{dotted_key}'. Expected format is 'section.key'."
            )
        section, key = dotted_key.split(".", 1)
        if not section or not key:
            raise ValueError(
                f"Invalid override key '{dotted_key}'. Expected format is 'section.key'."
            )
        if section not in allowed_sections:
            supported_sections = ", ".join(sorted(allowed_sections))
            raise ValueError(
                f"Unsupported override section '{section}' in '{dotted_key}'. "
                f"Supported sections are: {supported_sections}"
            )
        section_updates.setdefault(section, {})[key] = value

    updated = config
    for section, updates in section_updates.items():
        current = getattr(updated, section)
        updated = updated.model_copy(update={section: current.model_copy(update=updates)})

    # model_copy(update=...) skips validation, so revalidate before returning.
    return AppConfig.model_validate(updated.model_dump())
