from collections.abc import Sequence

from google import genai
from google.genai import types

from llm.exceptions import LLMResponseError
from llm.gemini_call import call_gemini
from rag.embeddings import EMBEDDING_DIMENSIONS, EmbeddingDocument

MAX_DOCUMENTS_PER_REQUEST = 100


def _query_text(text: str) -> str:
    return f"task: search result | query: {text}"


def _document_text(document: EmbeddingDocument) -> str:
    return f"title: {document.title or 'none'} | text: {document.text}"


class GeminiEmbeddingClient:
    def __init__(
        self, client: genai.Client, model: str, timeout_seconds: float
    ) -> None:
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    async def embed_documents(
        self, documents: Sequence[EmbeddingDocument]
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(documents), MAX_DOCUMENTS_PER_REQUEST):
            batch = documents[start : start + MAX_DOCUMENTS_PER_REQUEST]
            vectors.extend(await self._embed([_document_text(item) for item in batch]))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        (vector,) = await self._embed([_query_text(text)])
        return vector

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        response = await call_gemini(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=[
                    types.Content(parts=[types.Part(text=text)]) for text in texts
                ],
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMENSIONS
                ),
            ),
            self._timeout_seconds,
        )
        vectors = [
            list(embedding.values or []) for embedding in response.embeddings or []
        ]
        if len(vectors) != len(texts):
            raise LLMResponseError(
                f"expected {len(texts)} embeddings, got {len(vectors)}"
            )
        if any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
            raise LLMResponseError(
                f"embeddings are not {EMBEDDING_DIMENSIONS}-dimensional"
            )
        return vectors
