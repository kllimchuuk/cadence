import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from core.database import build_engine
from tests.helpers import alembic_config, drop_database, recreate_database

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def worktree_test_database_url(url: str) -> str:
    if not (REPOSITORY_ROOT / ".git").is_file():
        return url

    slug = re.sub(r"[^a-z0-9]+", "_", REPOSITORY_ROOT.name.lower().rsplit("-", 1)[-1])
    parsed = make_url(url)
    database = f'{parsed.database.removesuffix("_test")}_{slug}_test'

    return parsed.set(database=database).render_as_string(hide_password=False)


def pytest_configure() -> None:
    app_settings = Settings()
    name = make_url(app_settings.TEST_DATABASE_URL).database

    if not name or not name.endswith("_test"):
        pytest.exit(
            f"TEST_DATABASE_URL points at database {name!r}. The suite drops every "
            f"table in that database, so its name must end with '_test'.",
            returncode=4,
        )
    if app_settings.TEST_DATABASE_URL == app_settings.DATABASE_URL:
        pytest.exit(
            "TEST_DATABASE_URL is the same as DATABASE_URL. Running the suite "
            "would destroy the development database.",
            returncode=4,
        )


@pytest.fixture(scope="session")
def database_url() -> str:
    return worktree_test_database_url(Settings().TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def migrated_schema(database_url: str) -> Iterator[str]:
    recreate_database(database_url)
    command.upgrade(alembic_config(database_url), "head")
    yield database_url
    drop_database(database_url)


@pytest.fixture
def throwaway_database(database_url: str) -> Iterator[str]:
    parsed = make_url(database_url)
    url = parsed.set(database=f"{parsed.database}_migrations").render_as_string(
        hide_password=False
    )
    recreate_database(url)
    yield url
    drop_database(url)


@pytest_asyncio.fixture
async def session(migrated_schema: str) -> AsyncIterator[AsyncSession]:
    engine = build_engine(migrated_schema)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async_session = AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield async_session
            finally:
                await async_session.close()
                await transaction.rollback()
    finally:
        await engine.dispose()
