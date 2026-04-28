from pathlib import Path

from meeting_minutes.config import apply_overrides, load_config


def test_load_config_from_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[audio]
device = "BlackHole 2ch"
chunk_seconds = 5

[summarization]
ollama_model = "gemma4:latest"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.audio.device == "BlackHole 2ch"
    assert config.audio.chunk_seconds == 5
    assert config.summarization.ollama_model == "gemma4:latest"


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
        },
    )

    assert config.audio.device == "Mic"
    assert config.transcription.language == "en"
    assert config.summarization.ollama_model == "gemma4:e4b"
    assert not config.output.save_transcript
    assert config.chunking.chunk_size == 1000
