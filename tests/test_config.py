from pathlib import Path

import pytest

from meeting_minutes.config import (
    CleaningConfig,
    PreprocessingConfig,
    VadConfig,
    appconfig_section_names,
    apply_overrides,
    load_config,
)


def _make_different_value(value: object) -> object:
    """既定値とは異なる値を型に応じて生成する（override が実際に適用されたことを検証するため）。"""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return round(value + 0.1, 10)
    if isinstance(value, str):
        return value + "_override"
    if isinstance(value, Path):
        return Path(str(value) + "_override")
    if isinstance(value, list):
        return [*value, "_override"]
    return value


def test_load_config_from_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[audio]
device = "BlackHole 2ch"
chunk_seconds = 5
abort_on_overflow = false

[summarization]
ollama_model = "gemma4:latest"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.audio.device == "BlackHole 2ch"
    assert not config.preprocessing.enabled
    assert config.transcript_filter.enabled
    assert not config.vocabulary.dynamic_context_enabled
    assert config.audio.chunk_seconds == 5
    assert not config.audio.abort_on_overflow
    assert config.summarization.ollama_model == "gemma4:latest"


def test_example_config_loads() -> None:
    config = load_config(Path("config.example.toml"))

    assert config.audio.device == "BlackHole 2ch"


def test_apply_overrides_ignores_none() -> None:
    config = apply_overrides(load_config(None), {"audio.device": "Mic", "audio.sample_rate": None})

    assert config.audio.device == "Mic"
    assert config.audio.sample_rate == 16_000


def test_apply_overrides_updates_multiple_sections() -> None:
    config = apply_overrides(
        load_config(None),
        {
            "audio.device": "Mic",
            "transcription.language": "en",
            "summarization.ollama_model": "gemma4:e4b",
            "output.save_transcript": False,
            "chunking.chunk_size": 1000,
            "preprocessing.enabled": True,
            "transcript_filter.min_text_chars": 2,
            "vocabulary.dynamic_context_enabled": True,
        },
    )

    assert config.audio.device == "Mic"
    assert config.transcription.language == "en"
    assert config.summarization.ollama_model == "gemma4:e4b"
    assert not config.output.save_transcript
    assert config.chunking.chunk_size == 1000
    assert config.preprocessing.enabled
    assert config.transcript_filter.min_text_chars == 2
    assert config.vocabulary.dynamic_context_enabled


def test_preprocessing_config_rejects_invalid_peak() -> None:
    with pytest.raises(ValueError, match="target_peak"):
        PreprocessingConfig(target_peak=2.0)


def test_apply_overrides_raises_for_unknown_section() -> None:
    with pytest.raises(ValueError, match="Unsupported override section 'unknown'"):
        apply_overrides(load_config(None), {"unknown.value": "ignored"})


def test_vad_config_rejects_min_speech_longer_than_max() -> None:
    with pytest.raises(ValueError, match="min_speech_seconds"):
        VadConfig(min_speech_seconds=10, max_speech_seconds=3)


def test_vad_config_rejects_frame_longer_than_max() -> None:
    with pytest.raises(ValueError, match="frame_ms"):
        VadConfig(frame_ms=500, max_speech_seconds=0.1)


def test_example_config_loads_cleaning_section() -> None:
    config = load_config(Path("config.example.toml"))

    assert config.cleaning.chunk_size == 4000
    assert config.cleaning.output_filename == "transcript_clean.md"


def test_cleaning_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        CleaningConfig(**{"chunk_size": 4000, "chunk_overlap": 0})


def test_apply_overrides_accepts_all_appconfig_sections() -> None:
    """allowed_sections が AppConfig のネスト BaseModel セクションから動的に導出される。

    AppConfig に新セクション（ネスト BaseModel）を追加するだけで
    apply_overrides が自動対応することを確認する。
    """
    config = load_config(None)
    sections = appconfig_section_names()
    assert sections, "AppConfig には少なくとも 1 つのネスト BaseModel セクションが存在するはず"
    for section in sections:
        section_config = getattr(config, section)
        # None デフォルトのフィールドは apply_overrides が continue するため
        # override 経路を通らない。最初の non-None デフォルト値を持つフィールドを選ぶ。
        field_name, current_value = next(
            (
                (name, getattr(section_config, name))
                for name in type(section_config).model_fields
                if getattr(section_config, name) is not None
            ),
            (None, None),
        )
        assert field_name is not None, (
            f"section '{section}' に non-None デフォルト値を持つフィールドがない"
        )
        # 既定値と異なる値を渡すことで、override が実際に適用されたことを確認する。
        override_value = _make_different_value(current_value)
        result = apply_overrides(config, {f"{section}.{field_name}": override_value})
        assert getattr(getattr(result, section), field_name) == override_value
