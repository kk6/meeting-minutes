"""Ollama の `/api/generate` エンドポイントへの薄い同期クライアント。"""

from types import TracebackType

import httpx

from meeting_minutes.config import SummarizationConfig
from meeting_minutes.errors import OllamaError


class OllamaClient:
    """Ollama の non-streaming 補完 API を呼び出すコンテキストマネージャ。

    `httpx.Client` を遅延生成し、`with` ブロック終了時に確実に解放する。
    """

    def __init__(self, config: SummarizationConfig) -> None:
        self._config = config
        self._generate_url = f"{config.ollama_base_url.rstrip('/')}/api/generate"
        self._client: httpx.Client | None = None

    def __enter__(self) -> "OllamaClient":
        self._get_client()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._config.timeout_seconds)
        return self._client

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self._config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "think": self._config.think,
            "options": {
                "temperature": self._config.temperature,
                "num_ctx": self._config.num_ctx,
            },
        }
        try:
            response = self._get_client().post(
                self._generate_url,
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OllamaError(f"Ollama APIがエラーを返しました: {exc.response.text}") from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama APIに接続できませんでした: {exc}") from exc

        data = response.json()
        text = str(data.get("response", "")).strip()
        if not text:
            raise OllamaError("Ollama APIから空の応答が返りました")
        return text
