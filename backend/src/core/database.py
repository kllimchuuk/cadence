from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.requests import HTTPConnection

UTC_SERVER_SETTINGS = {"timezone": "UTC"}


def build_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"server_settings": UTC_SERVER_SETTINGS},
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )


def psycopg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def get_session_factory(
    conn: HTTPConnection,
) -> async_sessionmaker[AsyncSession]:
    return conn.app.state.session_factory


async def get_db(conn: HTTPConnection) -> AsyncIterator[AsyncSession]:
    async with conn.app.state.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
