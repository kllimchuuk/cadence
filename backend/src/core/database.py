from collections.abc import AsyncIterator

from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.requests import HTTPConnection

UTC_SERVER_SETTINGS = {"timezone": "UTC"}
_ASYNCPG_SSL_PARAMETER = "ssl"
_LIBPQ_SSL_PARAMETER = "sslmode"


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
    url = make_url(database_url).set(drivername="postgresql")
    ssl_mode = url.query.get(_ASYNCPG_SSL_PARAMETER)
    if ssl_mode is not None:
        url = url.difference_update_query([_ASYNCPG_SSL_PARAMETER]).update_query_dict(
            {_LIBPQ_SSL_PARAMETER: ssl_mode}
        )
    return url.render_as_string(hide_password=False)


def get_session_factory(
    conn: HTTPConnection,
) -> async_sessionmaker[AsyncSession]:
    return conn.app.state.session_factory


async def get_db(conn: HTTPConnection) -> AsyncIterator[AsyncSession]:
    async with get_session_factory(conn)() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
