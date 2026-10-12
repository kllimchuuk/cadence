from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from llm.client import LLMClient


@dataclass
class ConversationRuntimeContext:
    briefing_llm: LLMClient
    conversing_llm: LLMClient
    session_factory: async_sessionmaker[AsyncSession]


@dataclass
class AnalysisRuntimeContext:
    session_analysis_llm: LLMClient
    session_factory: async_sessionmaker[AsyncSession]
