from google import genai


class GeminiClient:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    async def generate(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model, contents=prompt
        )
        return response.text
