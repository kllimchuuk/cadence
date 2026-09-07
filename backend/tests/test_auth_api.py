import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from auth.constants import SESSION_COOKIE_NAME
from config import Settings
from main import create_app


def unique_email() -> str:
    return f"{uuid.uuid4()}@cadence.example"


@pytest.fixture
def client(migrated_schema: str) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=migrated_schema,
        CORS_ORIGINS="http://localhost:5173",
    )
    app = create_app(settings)

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def test_registering_creates_an_account_and_signs_in(client: TestClient) -> None:
    email = unique_email()

    response = client.post(
        "/auth/register", json={"email": email, "password": "a-strong-password"}
    )

    assert response.status_code == 201
    assert response.json()["email"] == email
    assert SESSION_COOKIE_NAME in response.cookies


def test_the_session_cookie_is_locked_down(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": unique_email(), "password": "a-strong-password"},
    )

    set_cookie = response.headers["set-cookie"]

    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_registering_the_same_email_twice_is_rejected(client: TestClient) -> None:
    email = unique_email()
    client.post(
        "/auth/register", json={"email": email, "password": "a-strong-password"}
    )

    response = client.post(
        "/auth/register", json={"email": email, "password": "another-password"}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_a_short_password_is_rejected_at_registration(client: TestClient) -> None:
    response = client.post(
        "/auth/register", json={"email": unique_email(), "password": "short"}
    )

    assert response.status_code == 422


def test_logging_in_with_the_right_password_succeeds(client: TestClient) -> None:
    email = unique_email()
    client.post(
        "/auth/register", json={"email": email, "password": "a-strong-password"}
    )
    client.cookies.clear()

    response = client.post(
        "/auth/login", json={"email": email, "password": "a-strong-password"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == email
    assert SESSION_COOKIE_NAME in response.cookies


def test_logging_in_with_the_wrong_password_is_rejected(client: TestClient) -> None:
    email = unique_email()
    client.post(
        "/auth/register", json={"email": email, "password": "a-strong-password"}
    )
    client.cookies.clear()

    response = client.post(
        "/auth/login", json={"email": email, "password": "the-wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_logging_in_as_an_unknown_user_fails_the_same_way(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": unique_email(), "password": "whatever-password"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_me_reflects_the_signed_in_user(client: TestClient) -> None:
    email = unique_email()
    client.post(
        "/auth/register", json={"email": email, "password": "a-strong-password"}
    )

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_without_a_session_is_unauthorized(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_logging_out_clears_the_session(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": unique_email(), "password": "a-strong-password"},
    )

    logout_response = client.post("/auth/logout")
    me_response = client.get("/auth/me")

    assert logout_response.status_code == 204
    assert me_response.status_code == 401


def test_one_users_session_cannot_read_another_users_data(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": unique_email(), "password": "a-strong-password"},
    )
    first_user_id = client.get("/auth/me").json()["id"]
    client.cookies.clear()

    client.post(
        "/auth/register",
        json={"email": unique_email(), "password": "a-strong-password"},
    )
    second_user_id = client.get("/auth/me").json()["id"]

    assert first_user_id != second_user_id
