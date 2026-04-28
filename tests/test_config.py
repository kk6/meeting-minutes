import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from meeting_minutes.config import apply_overrides, load_config


@pytest.fixture(autouse=True)
def clear_meeting_minutes_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in os.environ:
        if key.startswith("MEETING_MINUTES_"):
            monkeypatch.delenv(key, raising=False)
    yield


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


def test_apply_overrides_raises_for_unknown_section() -> None:
    with pytest.raises(ValueError, match="Unsupported override section 'unknown'"):
        apply_overrides(load_config(None), {"unknown.value": "ignored"})
