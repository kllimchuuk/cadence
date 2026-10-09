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
from orchestration.context import SessionRuntimeContext
from orchestration.session_runner import SessionRunner


def get_session_graph(conn: HTTPConnection) -> CompiledStateGraph:
    return conn.app.state.session_graph


def get_session_runtime_context(
    llm_factory: Annotated[LLMClientFactory, Depends(get_llm_client_factory)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionRuntimeContext:
    return SessionRuntimeContext(
        briefing_llm=llm_factory.create(settings.GEMINI_MODEL),
        conversing_llm=llm_factory.create(settings.GEMINI_MODEL),
        session_analysis_llm=llm_factory.create(settings.GEMINI_MODEL),
        session_factory=session_factory,
    )


def get_session_runner(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    runtime_context: Annotated[
        SessionRuntimeContext, Depends(get_session_runtime_context)
    ],
    graph: Annotated[CompiledStateGraph, Depends(get_session_graph)],
) -> SessionRunner:
    return SessionRunner(session_factory, runtime_context, graph)
