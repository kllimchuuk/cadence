import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

CHECKPOINTER_TABLES = frozenset(
    {
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
    }
)
_SETUP_LOCK_NAME = "cadence.checkpointer_setup"
_SETUP_LOCK_RETRY_SECONDS = 0.1


def is_checkpointer_table(name: str | None) -> bool:
    return name in CHECKPOINTER_TABLES


async def prepare_checkpointer(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    async with pool.connection() as connection:
        await _wait_for_setup_lock(connection)
        try:
            await AsyncPostgresSaver(connection).setup()
        finally:
            await connection.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", (_SETUP_LOCK_NAME,)
            )
    return AsyncPostgresSaver(pool)


async def _wait_for_setup_lock(connection: AsyncConnection) -> None:
    while not await _try_setup_lock(connection):
        await asyncio.sleep(_SETUP_LOCK_RETRY_SECONDS)


async def _try_setup_lock(connection: AsyncConnection) -> bool:
    cursor = await connection.execute(
        "SELECT pg_try_advisory_lock(hashtext(%s))", (_SETUP_LOCK_NAME,)
    )
    (acquired,) = await cursor.fetchone()
    return acquired
