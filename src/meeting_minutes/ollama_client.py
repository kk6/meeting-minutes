import httpx

from meeting_minutes.config import SummarizationConfig
from meeting_minutes.errors import OllamaError


class OllamaClient:
    def __init__(self, config: SummarizationConfig) -> None:
        self._config = config
        self._generate_url = f"{config.ollama_base_url.rstrip('/')}/api/generate"

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self._config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self._config.temperature,
                "num_ctx": self._config.num_ctx,
            },
        }
        try:
            response = httpx.post(
                self._generate_url,
                json=payload,
                timeout=self._config.timeout_seconds,
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
