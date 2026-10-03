from typing import Annotated

from fastapi import Depends
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import HTTPConnection

from core.database import get_session_factory
from llm.dependencies import get_llm_client_factory
from llm.factory import LLMClientFactory
from orchestration.context import SessionRuntimeContext
from orchestration.session_runner import SessionRunner

_FLASH_MODEL = "gemini-flash-latest"


def get_checkpointer(conn: HTTPConnection) -> AsyncPostgresSaver:
    return conn.app.state.checkpointer


def get_session_runtime_context(
    llm_factory: Annotated[LLMClientFactory, Depends(get_llm_client_factory)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> SessionRuntimeContext:
    return SessionRuntimeContext(
        briefing_llm=llm_factory.create(_FLASH_MODEL),
        conversing_llm=llm_factory.create(_FLASH_MODEL),
        session_analysis_llm=llm_factory.create(_FLASH_MODEL),
        session_factory=session_factory,
    )


def get_session_runner(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    runtime_context: Annotated[
        SessionRuntimeContext, Depends(get_session_runtime_context)
    ],
    checkpointer: Annotated[AsyncPostgresSaver, Depends(get_checkpointer)],
) -> SessionRunner:
    return SessionRunner(session_factory, runtime_context, checkpointer)
