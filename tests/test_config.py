from pathlib import Path

import pytest

from meeting_minutes.config import PreprocessingConfig, VadConfig, apply_overrides, load_config


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
