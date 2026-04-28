import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def clear_meeting_minutes_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("MEETING_MINUTES_"):
            monkeypatch.delenv(key, raising=False)
    yield
