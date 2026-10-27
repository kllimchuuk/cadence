import asyncio

from config import settings
from core.database import build_engine, build_session_factory
from llm.factory import LLMClientFactory
from rag.corpus import load_corpus
from rag.ingestion import ContentIngestionService
from rag.repository import ContentChunkRepositoryImpl
from rag.retrying_embedder import RetryingEmbeddingClient

EMBEDDING_MAX_ATTEMPTS = 5
EMBEDDING_BASE_DELAY_SECONDS = 2.0


async def main() -> None:
    engine = build_engine(settings.DATABASE_URL)
    llm_factory = LLMClientFactory(
        settings.GEMINI_API_KEY, settings.LLM_TIMEOUT_SECONDS
    )
    try:
        async with build_session_factory(engine)() as session:
            service = ContentIngestionService(
                ContentChunkRepositoryImpl(session),
                RetryingEmbeddingClient(
                    llm_factory.create_embedding_client(
                        settings.GEMINI_EMBEDDING_MODEL
                    ),
                    EMBEDDING_MAX_ATTEMPTS,
                    EMBEDDING_BASE_DELAY_SECONDS,
                ),
                session.commit,
            )
            report = await service.ingest(load_corpus())
    finally:
        await engine.dispose()
    print(
        f"embedded={report.embedded} unchanged={report.unchanged} "
        f"removed={report.removed} batches={report.batches}"
    )


if __name__ == "__main__":
    asyncio.run(main())
