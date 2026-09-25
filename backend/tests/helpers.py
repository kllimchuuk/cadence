import asyncio
from pathlib import Path
from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, make_url

from core.database import build_engine
from core.registry import metadata

BACKEND_DIR = Path(__file__).resolve().parents[1]


def settings_kwargs(**overrides: str) -> dict[str, str]:
    kwargs = {
        "APP_HOST": "127.0.0.1",
        "APP_PORT": "8000",
        "CORS_ORIGINS": "http://localhost:5173",
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cadence",
        "TEST_DATABASE_URL": (
            "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cadence_test"
        ),
        "SECRET_KEY": "test-secret-key",
        "SECURE_COOKIES": "true",
        "FRONTEND_URL": "http://localhost:5173",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "GOOGLE_SERVER_METADATA_URL": (
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        "GEMINI_API_KEY": "test-gemini-api-key",
    }
    kwargs.update(overrides)
    return kwargs


def alembic_config(url: str) -> Config:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["sqlalchemy.url"] = url
    return config


async def _on_maintenance_database(url: str, statement: str) -> None:
    admin_url = make_url(url).set(database="postgres")
    engine = build_engine(
        admin_url.render_as_string(hide_password=False)
    ).execution_options(isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


def drop_database(url: str) -> None:
    name = make_url(url).database
    asyncio.run(
        _on_maintenance_database(url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    )


def recreate_database(url: str) -> None:
    drop_database(url)
    name = make_url(url).database
    asyncio.run(_on_maintenance_database(url, f'CREATE DATABASE "{name}"'))


async def _read(url: str, reader) -> Any:
    engine = build_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(reader)
    finally:
        await engine.dispose()


def table_names(url: str) -> list[str]:
    return asyncio.run(_read(url, lambda c: inspect(c).get_table_names()))


def _diff(connection: Connection) -> list:
    context = MigrationContext.configure(
        connection,
        opts={"compare_type": True, "compare_server_default": True},
    )
    return compare_metadata(context, metadata)


def schema_diff(url: str) -> list:
    return asyncio.run(_read(url, _diff))
