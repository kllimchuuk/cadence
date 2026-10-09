import asyncio

import pytest
from psycopg_pool import AsyncConnectionPool

from core.database import psycopg_dsn
from orchestration.checkpointer import is_checkpointer_table, prepare_checkpointer

CONCURRENT_WORKERS = 4


@pytest.mark.asyncio
async def test_concurrent_workers_prepare_the_checkpointer_without_racing(
    throwaway_database: str,
) -> None:
    pools = [
        AsyncConnectionPool(
            conninfo=psycopg_dsn(throwaway_database),
            open=False,
            kwargs={"autocommit": True},
        )
        for _ in range(CONCURRENT_WORKERS)
    ]
    for pool in pools:
        await pool.open()

    try:
        await asyncio.gather(*(prepare_checkpointer(pool) for pool in pools))
        async with pools[0].connection() as connection:
            cursor = await connection.execute(
                "SELECT count(*), count(DISTINCT v) FROM checkpoint_migrations"
            )
            applied, distinct = await cursor.fetchone()
    finally:
        for pool in pools:
            await pool.close()

    assert applied == distinct


def test_langgraph_checkpoint_tables_are_recognised() -> None:
    assert is_checkpointer_table("checkpoints")
    assert is_checkpointer_table("checkpoint_writes")


def test_an_application_table_sharing_the_prefix_is_not_a_checkpointer_table() -> None:
    assert not is_checkpointer_table("checkpoint_notes")
    assert not is_checkpointer_table("learning_sessions")
    assert not is_checkpointer_table(None)
