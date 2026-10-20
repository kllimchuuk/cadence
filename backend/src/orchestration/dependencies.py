from typing import Annotated

from fastapi import Depends
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import HTTPConnection

from auth.dependencies import get_settings
from config import Settings
from core.database import get_session_factory
from llm.dependencies import get_llm_client_factory
from llm.factory import LLMClientFactory
from orchestration.analysis_runner import SessionAnalysisRunner
from orchestration.context import AnalysisRuntimeContext, ConversationRuntimeContext
from orchestration.session_runner import SessionRunner


def get_conversation_graph(conn: HTTPConnection) -> CompiledStateGraph:
    return conn.app.state.conversation_graph


def get_analysis_graph(conn: HTTPConnection) -> CompiledStateGraph:
    return conn.app.state.analysis_graph


def get_conversation_runtime_context(
    llm_factory: Annotated[LLMClientFactory, Depends(get_llm_client_factory)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationRuntimeContext:
    return ConversationRuntimeContext(
        briefing_llm=llm_factory.create(settings.GEMINI_MODEL),
        conversing_llm=llm_factory.create(settings.GEMINI_MODEL),
        embedder=llm_factory.create_embedding_client(settings.GEMINI_EMBEDDING_MODEL),
        session_factory=session_factory,
    )


def get_analysis_runtime_context(
    llm_factory: Annotated[LLMClientFactory, Depends(get_llm_client_factory)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisRuntimeContext:
    return AnalysisRuntimeContext(
        session_analysis_llm=llm_factory.create(settings.GEMINI_MODEL),
        embedder=llm_factory.create_embedding_client(settings.GEMINI_EMBEDDING_MODEL),
        session_factory=session_factory,
    )


def get_session_runner(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    runtime_context: Annotated[
        ConversationRuntimeContext, Depends(get_conversation_runtime_context)
    ],
    graph: Annotated[CompiledStateGraph, Depends(get_conversation_graph)],
) -> SessionRunner:
    return SessionRunner(session_factory, runtime_context, graph)


def get_session_analysis_runner(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    runtime_context: Annotated[
        AnalysisRuntimeContext, Depends(get_analysis_runtime_context)
    ],
    graph: Annotated[CompiledStateGraph, Depends(get_analysis_graph)],
) -> SessionAnalysisRunner:
    return SessionAnalysisRunner(session_factory, runtime_context, graph)
