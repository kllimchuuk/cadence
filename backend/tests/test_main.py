from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from config import Settings
from core.exceptions import AppException
from main import create_app
from tests.helpers import settings_kwargs


class DeckNotFound(AppException):
    status_code = 404


PROBE_PREFIX = "/__test__"


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, **settings_kwargs())


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)

    @app.get(f"{PROBE_PREFIX}/app-exception")
    async def raise_app_exception() -> None:
        raise AppException(
            code="test_error",
            message="Test error",
            payload={"field": "value"},
        )

    @app.get(f"{PROBE_PREFIX}/not-found")
    async def raise_not_found() -> None:
        raise DeckNotFound(code="deck_not_found", message="Deck not found")

    @app.get(f"{PROBE_PREFIX}/unhandled")
    async def raise_unhandled() -> None:
        raise ValueError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_app_exception_returns_error_contract(client: TestClient) -> None:
    response = client.get(f"{PROBE_PREFIX}/app-exception")

    assert response.status_code == 500
    assert response.json() == {
        "code": "test_error",
        "message": "Test error",
        "payload": {"field": "value"},
    }


def test_app_exception_uses_its_own_status_code(client: TestClient) -> None:
    response = client.get(f"{PROBE_PREFIX}/not-found")

    assert response.status_code == 404
    assert response.json()["code"] == "deck_not_found"


def test_unhandled_exception_is_not_leaked(client: TestClient) -> None:
    response = client.get(f"{PROBE_PREFIX}/unhandled")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "payload": {},
    }
    assert "boom" not in response.text


def test_settings_ignore_the_local_env_file() -> None:
    assert Settings(_env_file=None, **settings_kwargs()).APP_PORT == 8000


def test_cors_origins_are_split_and_stripped() -> None:
    kwargs = settings_kwargs(CORS_ORIGINS="http://a.test, http://b.test, ")
    parsed = Settings(_env_file=None, **kwargs).cors_origins

    assert parsed == ["http://a.test", "http://b.test"]


def test_a_missing_secret_key_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **settings_kwargs(SECRET_KEY=""))


def test_a_missing_required_field_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_HOST", raising=False)
    kwargs = {
        key: value for key, value in settings_kwargs().items() if key != "APP_HOST"
    }
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)
