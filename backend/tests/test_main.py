from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from core.exceptions import AppException
from main import app

PROBE_PREFIX = "/__test__"


@pytest.fixture
def client() -> Iterator[TestClient]:
    @app.get(f"{PROBE_PREFIX}/app-exception")
    async def raise_app_exception() -> None:
        raise AppException(
            code="test_error",
            message="Test error",
            payload={"field": "value"},
        )

    @app.get(f"{PROBE_PREFIX}/unhandled")
    async def raise_unhandled() -> None:
        raise ValueError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.router.routes = [
        route
        for route in app.router.routes
        if not getattr(route, "path", "").startswith(PROBE_PREFIX)
    ]


def test_app_exception_returns_error_contract(client: TestClient) -> None:
    response = client.get(f"{PROBE_PREFIX}/app-exception")

    assert response.status_code == 500
    assert response.json() == {
        "code": "test_error",
        "message": "Test error",
        "payload": {"field": "value"},
    }


def test_unhandled_exception_is_not_leaked(client: TestClient) -> None:
    response = client.get(f"{PROBE_PREFIX}/unhandled")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "payload": {},
    }
    assert "boom" not in response.text
