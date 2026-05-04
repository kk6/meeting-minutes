import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def isolate_user_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """ホストの環境変数・ XDG ディレクトリをテストから隔離する。

    - `MEETING_MINUTES_*` 環境変数をすべて剥がす（pydantic-settings の暗黙上書き防止）。
    - `XDG_CONFIG_HOME` / `XDG_DATA_HOME` をテストごとの空ディレクトリに固定し、
      ホストに `~/.config/meeting-minutes/config.toml` が存在しても auto-discovery が
      ヒットしないようにする。
    """
    for key in list(os.environ):
        if key.startswith("MEETING_MINUTES_"):
            monkeypatch.delenv(key, raising=False)
    isolation_root = tmp_path_factory.mktemp("xdg_isolation")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(isolation_root / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(isolation_root / "data"))
    yield
