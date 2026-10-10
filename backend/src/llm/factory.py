from google import genai

from llm.client import LLMClient
from llm.gemini_client import GeminiClient


class LLMClientFactory:
    def __init__(self, api_key: str, timeout_seconds: float) -> None:
        self._client = genai.Client(api_key=api_key)
        self._timeout_seconds = timeout_seconds

    def create(self, model: str) -> LLMClient:
        return GeminiClient(self._client, model, self._timeout_seconds)
