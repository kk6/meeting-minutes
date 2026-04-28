import json
from datetime import datetime
from pathlib import Path

import pytest

from meeting_minutes.config import load_config
from meeting_minutes.devices import InputDevice
from meeting_minutes.metadata import build_metadata, write_metadata


def test_write_metadata_serializes_datetime_and_path(tmp_path: Path) -> None:
    started_at = datetime(2026, 4, 28, 10, 0, 0, 123456)
    ended_at = datetime(2026, 4, 28, 10, 0, 8, 654321)
    transcript_path = tmp_path / "transcript_live.md"
    metadata = build_metadata(
        started_at=started_at,
        ended_at=ended_at,
        input_device=InputDevice(
            index=1,
            name="Mic",
            channels=1,
            default_sample_rate=16000,
            is_blackhole=False,
        ),
        config=load_config(None),
        transcript_path=transcript_path,
        errors=[],
    )
    output = tmp_path / "metadata.json"

    write_metadata(output, metadata)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["started_at"] == "2026-04-28T10:00:00"
    assert data["ended_at"] == "2026-04-28T10:00:08"
    assert data["transcript_path"] == str(transcript_path)
    assert data["processing_seconds"] == pytest.approx(8.530865)
