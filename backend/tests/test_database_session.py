import asyncio
from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from core.database import build_engine, build_session_factory, get_db
from main import create_app
from tests.helpers import settings_kwargs
from users.models import User
from users.repository import UserRepositoryImpl

PROBE_PREFIX = "/__test__"


@pytest.fixture
def client(migrated_schema: str) -> Iterator[TestClient]:
    app = create_app(
        Settings(_env_file=None, **settings_kwargs(DATABASE_URL=migrated_schema))
    )

    @app.post(f"{PROBE_PREFIX}/users")
    async def create_user(
        email: str, db: Annotated[AsyncSession, Depends(get_db)]
    ) -> dict[str, str]:
        user = await UserRepositoryImpl(db).create(
            email=email,
            first_name="Test",
            last_name="User",
            nickname=email.split("@")[0],
            hashed_password="hashed",
        )
        return {"id": str(user.id)}

    @app.post(f"{PROBE_PREFIX}/users-then-fail")
    async def create_user_then_fail(
        email: str, db: Annotated[AsyncSession, Depends(get_db)]
    ) -> None:
        await UserRepositoryImpl(db).create(
            email=email,
            first_name="Test",
            last_name="User",
            nickname=email.split("@")[0],
            hashed_password="hashed",
        )
        raise ValueError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    _run(migrated_schema, "TRUNCATE users CASCADE")


def _run(url: str, statement: str) -> None:
    async def execute() -> None:
        engine = build_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(statement))
        finally:
            await engine.dispose()

    asyncio.run(execute())


def _count(url: str, email: str) -> int:
    async def query() -> int:
        engine = build_engine(url)
        try:
            async with engine.connect() as connection:
                return await connection.scalar(
                    text("SELECT count(*) FROM users WHERE email = :email"),
                    {"email": email},
                )
        finally:
            await engine.dispose()

    return asyncio.run(query())


def test_a_successful_request_commits(client: TestClient, migrated_schema: str) -> None:
    response = client.post(f"{PROBE_PREFIX}/users", params={"email": "ok@cadence.test"})

    assert response.status_code == 200
    assert _count(migrated_schema, "ok@cadence.test") == 1


def test_a_failed_request_rolls_back(client: TestClient, migrated_schema: str) -> None:
    response = client.post(
        f"{PROBE_PREFIX}/users-then-fail", params={"email": "rolled@cadence.test"}
    )

    assert response.status_code == 500
    assert _count(migrated_schema, "rolled@cadence.test") == 0


def test_updated_at_moves_on_a_later_transaction(migrated_schema: str) -> None:
    async def scenario() -> tuple:
        engine = build_engine(migrated_schema)
        session_factory = build_session_factory(engine)
        try:
            async with session_factory() as session:
                user = await UserRepositoryImpl(session).create(
                    email="bumped@cadence.test",
                    first_name="Bumped",
                    last_name="User",
                    nickname="bumped",
                    hashed_password="hashed",
                )
                await session.commit()
                created_at, first = user.created_at, user.updated_at

            async with session_factory() as session:
                stored = await session.scalar(
                    select(User).where(User.email == "bumped@cadence.test")
                )
                stored.ui_language = "en"
                await session.commit()
                await session.refresh(stored)
                return created_at, first, stored.updated_at
        finally:
            await engine.dispose()

    created_at, first, second = asyncio.run(scenario())
    _run(migrated_schema, "TRUNCATE users CASCADE")

    assert first == created_at
    assert second > first
