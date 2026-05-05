"""アプリ全体の設定を pydantic モデルで定義し、TOML / 環境変数 / CLI 上書きから組み立てる。"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config init で雛形として配るファイル。`src/meeting_minutes/config/templates/` 配下に置き、
# `importlib.resources` でパッケージデータとして参照する（インストール後の wheel でも解決する）。
_TEMPLATE_FILENAME = "config.example.toml"


def _xdg_dir(env_var: str, fallback: Path) -> Path:
    """XDG 環境変数を読み取り、絶対パスのときだけ採用する。

    XDG Base Directory 仕様では相対パスは無効扱いとされており、設定ミスで相対値が
    入った場合に成果物の保存先が cwd 依存になるのを防ぐため fallback に切り替える。
    """
    value = os.environ.get(env_var)
    if value:
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
    return fallback


def _xdg_config_home() -> Path:
    """`$XDG_CONFIG_HOME` を返す。未設定または相対値なら `~/.config` を返す。"""
    return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config")


def _xdg_data_home() -> Path:
    """`$XDG_DATA_HOME` を返す。未設定または相対値なら `~/.local/share` を返す。"""
    return _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")


def default_config_path() -> Path:
    """`load_config(None)` が auto-discovery で参照する設定ファイルのパスを返す。"""
    return _xdg_config_home() / "meeting-minutes" / "config.toml"


def _default_output_dir() -> Path:
    """セッション成果物の既定出力先を返す（XDG_DATA_HOME ベース）。"""
    return _xdg_data_home() / "meeting-minutes" / "output"


class AudioConfig(BaseModel):
    """マイク入力（デバイス、サンプリング、チャンク長、オーバーフロー扱い）の設定。"""

    device: str | None = None
    device_index: int | None = None
    sample_rate: int = 16_000
    channels: int = 1
    chunk_seconds: int = Field(default=8, ge=1)
    abort_on_overflow: bool = True


class VadConfig(BaseModel):
    """VAD（音声区間検出）のフレーム長・閾値・最小／最大発話長の設定。"""

    enabled: bool = True
    frame_ms: int = Field(default=30, ge=10)
    speech_threshold: float = Field(default=0.01, gt=0)
    silence_seconds: float = Field(default=0.8, ge=0)
    min_speech_seconds: float = Field(default=0.3, ge=0)
    max_speech_seconds: float = Field(default=15.0, gt=0)
    padding_seconds: float = Field(default=0.2, ge=0)

    @model_validator(mode="after")
    def validate_durations(self) -> Self:
        frame_seconds = self.frame_ms / 1000
        if self.min_speech_seconds > self.max_speech_seconds:
            raise ValueError(
                "vad.min_speech_seconds must be less than or equal to max_speech_seconds"
            )
        if frame_seconds > self.max_speech_seconds:
            raise ValueError(
                "vad.frame_ms converted to seconds must be less than or equal to max_speech_seconds"
            )
        return self


class PreprocessingConfig(BaseModel):
    """前処理（ノイズゲート、ピーク正規化）の有効化と閾値設定。"""

    enabled: bool = False
    normalize_peak: bool = True
    target_peak: float = Field(default=0.8, gt=0, le=1.0)
    noise_gate_enabled: bool = False
    noise_gate_threshold: float = Field(default=0.003, ge=0)


class TranscriptionConfig(BaseModel):
    """Whisper モデル名・言語・実行デバイス・量子化設定。"""

    whisper_model: str = "small"
    language: str = "ja"
    device: str = "cpu"
    compute_type: str = "int8"


class TranscriptFilterConfig(BaseModel):
    """Whisper の幻聴・常套句・反復パターン除去のしきい値とデフォルト常套句。"""

    enabled: bool = True
    canned_false_positives: list[str] = Field(
        default_factory=lambda: [
            "Thank you.",
            "Thanks for watching.",
            "Bye.",
        ],
    )
    min_text_chars: int = Field(default=0, ge=0)
    max_repeat_pattern_chars: int = Field(default=8, ge=1)
    min_repeat_count: int = Field(default=4, ge=2)


class SummarizationConfig(BaseModel):
    """要約に用いる Ollama のエンドポイント・モデル・推論パラメータ設定。"""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4"
    temperature: float = 0.2
    num_ctx: int = 8192
    timeout_seconds: float = 600
    # gemma4 等の thinking 対応モデルはデフォルトで推論トークンを大量生成し
    # num_ctx を使い切って response が空になるため、デフォルトで無効化する。
    think: bool = False


class OutputConfig(BaseModel):
    """成果物（文字起こし、音声）の出力ディレクトリと保存可否の設定。"""

    base_dir: Path = Field(default_factory=_default_output_dir)
    save_transcript: bool = True
    save_audio: bool = True


class ChunkingConfig(BaseModel):
    """要約時に長文を分割するチャンクサイズと重複量の設定。"""

    chunk_size: int = 6000
    chunk_overlap: int = 500


class VocabularyConfig(BaseModel):
    """参加者・用語ファイルのパスとプロンプト注入時の文字数制限。"""

    glossary_file: Path | None = None
    participants_file: Path | None = None
    # Whisper の initial_prompt は約 224 token が上限。日本語では 1 文字 ≒ 1〜2 token のため、
    # 200 文字を安全側のデフォルトとする。
    max_prompt_chars: int = Field(default=200, ge=0)
    dynamic_context_enabled: bool = False
    dynamic_context_chars: int = Field(default=120, ge=0)
    # 要約プロンプトへの語彙注入上限。Ollama の num_ctx を圧迫しないよう項目単位で切り落とす。
    # 0 で語彙セクションを無効化する。
    max_summary_chars: int = Field(default=1000, ge=0)


class CleaningConfig(BaseModel):
    """文字起こし整形（clean）コマンドのチャンク化と出力設定。"""

    # 廃止済みフィールド（chunk_overlap 等）を設定ファイルに残したままにすると
    # サイレントに無視される。extra='forbid' で未知フィールドを即座にエラーにし、
    # ユーザーが設定の不整合に気づけるようにする。
    model_config = ConfigDict(extra="forbid")

    chunk_size: int = Field(default=4000, ge=100)
    output_filename: str = "transcript_clean.md"


class AppConfig(BaseSettings):
    """全セクションを束ねるアプリ設定。

    `MEETING_MINUTES_<SECTION>__<KEY>` 形式の環境変数で各セクションの値を上書き可能。
    """

    model_config = SettingsConfigDict(env_prefix="MEETING_MINUTES_", env_nested_delimiter="__")

    audio: AudioConfig = Field(default_factory=AudioConfig)
    vad: VadConfig = Field(default_factory=VadConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    transcript_filter: TranscriptFilterConfig = Field(default_factory=TranscriptFilterConfig)
    summarization: SummarizationConfig = Field(default_factory=SummarizationConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    vocabulary: VocabularyConfig = Field(default_factory=VocabularyConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)


ConfigSourceKind = Literal["explicit", "auto_discovered", "defaults"]


@dataclass(frozen=True)
class ConfigSource:
    """`load_config` がどこから設定を読み込んだかを示すメタデータ。

    `daemon serve` 起動時のログ出力や `meeting-minutes config path` コマンドが、
    auto-discovery と明示指定と組み込み既定値のみの 3 パターンを区別するために使う。
    """

    kind: ConfigSourceKind
    path: Path | None


def resolve_config_source(path: Path | None) -> ConfigSource:
    """`load_config(path)` が参照する設定ソースを返す。読み込みは行わない。

    - `path` が指定された場合: `kind="explicit"`、`path` をそのまま返す（存在チェックなし）。
    - `path` が None で XDG 既定パスに config.toml が「ファイルとして」ある場合:
      `kind="auto_discovered"`。同名のディレクトリは auto-discovery 対象から除外する。
    - 上記いずれでもない場合: `kind="defaults"`、`path=None`。
    """
    if path is not None:
        return ConfigSource(kind="explicit", path=path)
    candidate = default_config_path()
    if candidate.is_file():
        return ConfigSource(kind="auto_discovered", path=candidate)
    return ConfigSource(kind="defaults", path=None)


def read_template_config_text() -> str:
    """`config init` で雛形として書き出す `config.example.toml` の内容を返す。

    `importlib.resources` 経由で取得することで、リポジトリ内実行・editable install・
    `uv tool install .` 後の wheel いずれの形態でも解決される。
    """
    from importlib.resources import files

    return files(__package__).joinpath("templates", _TEMPLATE_FILENAME).read_text(encoding="utf-8")


def load_config(path: Path | None) -> AppConfig:
    """TOML から `AppConfig` を構築する。

    `path` が None の場合、まず `$XDG_CONFIG_HOME/meeting-minutes/config.toml`
    （未設定時は `~/.config/meeting-minutes/config.toml`）を参照する。
    存在しなければ環境変数と既定値のみで構築する。

    値の優先順位は env (`MEETING_MINUTES_*`) > TOML > 組み込み既定値。
    `path` の不在・読み込み失敗・パース失敗・バリデーション失敗時は対応する例外を送出する。
    """
    if path is None:
        candidate = default_config_path()
        # ディレクトリ等の同名エントリで auto-discovery がヒットしないよう is_file() を使う。
        if candidate.is_file():
            path = candidate
        else:
            return AppConfig()
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")

    return _load_appconfig_with_toml(path)


# TOML 中で相対パスとして書かれた場合に config ファイルのディレクトリを基準に絶対化する
# フィールド。プロセスの cwd ではなく config の場所を基準にすることで、グローバル実行
# （任意 cwd）でも同じ config が同じ場所を指す。env 由来の値はユーザー意図を尊重するため
# 変換しない。
_PATH_FIELDS_TO_ANCHOR: tuple[tuple[str, str], ...] = (
    ("output", "base_dir"),
    ("vocabulary", "glossary_file"),
    ("vocabulary", "participants_file"),
)


def _load_appconfig_with_toml(path: Path) -> AppConfig:
    """env > TOML > defaults の優先順で `AppConfig` を構築する。

    `_AnchoredTomlSource` を `env_settings` の下、`defaults` の上に挟み込み、
    TOML 値の上に環境変数を載せる。TOML 中の相対パスは config ファイルの
    ディレクトリ基準で絶対化されるが、env 由来の値はそのまま採用する。
    `toml_file` はクラス属性として渡す必要があるため、呼び出しごとに
    `AppConfig` のサブクラスを動的生成する。
    """
    from typing import Any

    from pydantic_settings import PydanticBaseSettingsSource, TomlConfigSettingsSource

    anchor = path.parent.resolve()

    class _AnchoredTomlSource(TomlConfigSettingsSource):
        """TOML 中の相対パスを config ディレクトリ基準で絶対化する設定ソース。"""

        def __call__(self) -> dict[str, Any]:
            data = super().__call__()
            for section_name, field_name in _PATH_FIELDS_TO_ANCHOR:
                section = data.get(section_name)
                if not isinstance(section, dict):
                    continue
                value = section.get(field_name)
                if value is None:
                    continue
                p = Path(str(value))
                if not p.is_absolute():
                    section[field_name] = str((anchor / p).resolve())
            return data

    class _ConfigWithToml(AppConfig):
        model_config = SettingsConfigDict(
            env_prefix="MEETING_MINUTES_",
            env_nested_delimiter="__",
            toml_file=str(path),
        )

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (
                init_settings,
                env_settings,
                _AnchoredTomlSource(settings_cls),
                dotenv_settings,
                file_secret_settings,
            )

    return _ConfigWithToml()


def appconfig_section_names() -> set[str]:
    """`AppConfig` のうち、ネストされた `BaseModel` セクション（上書き対象）の名前集合を返す。

    `apply_overrides` の `current.model_copy(...)` はネストモデル前提のため、
    将来 `AppConfig` に非モデルフィールド（例: `debug: bool`）が追加されても
    対象に含まれないようフィルタする。
    """
    return {
        name
        for name, field in AppConfig.model_fields.items()
        if isinstance(field.annotation, type) and issubclass(field.annotation, BaseModel)
    }


def apply_overrides(config: AppConfig, overrides: dict[str, object]) -> AppConfig:
    """`section.key` 形式の上書きを適用した新しい `AppConfig` を返す。

    Raises:
        ValueError: キー形式が不正、または未知のセクションが指定された場合。
        pydantic.ValidationError: 上書き値が型・制約に合わない場合（再検証時）。
    """
    allowed_sections = appconfig_section_names()
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
