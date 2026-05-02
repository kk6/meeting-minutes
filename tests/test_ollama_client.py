"""OllamaClient のリクエストペイロードと応答処理を検証するテスト。"""

import json

import httpx
import pytest

from meeting_minutes.config import SummarizationConfig
from meeting_minutes.errors import OllamaError
from meeting_minutes.ollama_client import OllamaClient


def _make_response(body: dict) -> httpx.Response:
    return httpx.Response(200, json=body, request=httpx.Request("POST", "http://localhost"))


def test_generate_sends_think_false_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    def fake_post(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        sent.append(json.loads(json.dumps(kwargs.get("json", {}))))
        return _make_response({"response": "ok"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with OllamaClient(SummarizationConfig()) as client:
        client.generate("hello")

    assert len(sent) == 1
    assert sent[0]["think"] is False


def test_generate_sends_think_true_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    def fake_post(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        sent.append(json.loads(json.dumps(kwargs.get("json", {}))))
        return _make_response({"response": "ok"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with OllamaClient(SummarizationConfig(think=True)) as client:
        client.generate("hello")

    assert sent[0]["think"] is True


def test_generate_raises_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        return _make_response({"response": ""})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with OllamaClient(SummarizationConfig()) as client:
        with pytest.raises(OllamaError, match="空の応答"):
            client.generate("hello")
