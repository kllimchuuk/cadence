import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from auth.constants import SESSION_COOKIE_NAME
from config import Settings
from main import create_app
from tests.helpers import settings_kwargs


def unique_email() -> str:
    return f"{uuid.uuid4()}@cadence.example"


def unique_nickname() -> str:
    return f"learner{uuid.uuid4().hex[:12]}"


def register_payload(**overrides: str) -> dict:
    payload = {
        "email": unique_email(),
        "password": "a-strong-password",
        "first_name": "Test",
        "last_name": "User",
        "nickname": unique_nickname(),
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def client(migrated_schema: str) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, **settings_kwargs(DATABASE_URL=migrated_schema))
    app = create_app(settings)

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def test_registering_creates_an_account_and_signs_in(client: TestClient) -> None:
    payload = register_payload()

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]
    assert response.json()["first_name"] == payload["first_name"]
    assert response.json()["last_name"] == payload["last_name"]
    assert response.json()["nickname"] == payload["nickname"]
    assert SESSION_COOKIE_NAME in response.cookies


def test_the_session_cookie_is_locked_down(client: TestClient) -> None:
    response = client.post("/auth/register", json=register_payload())

    set_cookie = response.headers["set-cookie"]

    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_registering_the_same_email_twice_is_rejected(client: TestClient) -> None:
    email = unique_email()
    client.post("/auth/register", json=register_payload(email=email))

    response = client.post(
        "/auth/register",
        json=register_payload(email=email, password="another-password"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_registering_the_same_nickname_twice_is_rejected(client: TestClient) -> None:
    nickname = unique_nickname()
    client.post("/auth/register", json=register_payload(nickname=nickname))

    response = client.post("/auth/register", json=register_payload(nickname=nickname))

    assert response.status_code == 409
    assert response.json()["code"] == "nickname_already_taken"


def test_a_short_password_is_rejected_at_registration(client: TestClient) -> None:
    response = client.post("/auth/register", json=register_payload(password="short"))

    assert response.status_code == 422


def test_a_missing_first_name_is_rejected_at_registration(
    client: TestClient,
) -> None:
    payload = register_payload()
    del payload["first_name"]

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_a_non_latin_nickname_is_rejected_at_registration(
    client: TestClient,
) -> None:
    response = client.post("/auth/register", json=register_payload(nickname="Нікіта"))

    assert response.status_code == 422


def test_a_cyrillic_name_is_accepted_at_registration(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json=register_payload(first_name="Нікіта", last_name="Клімчук"),
    )

    assert response.status_code == 201
    assert response.json()["first_name"] == "Нікіта"
    assert response.json()["last_name"] == "Клімчук"


def test_logging_in_with_the_right_password_succeeds(client: TestClient) -> None:
    email = unique_email()
    client.post("/auth/register", json=register_payload(email=email))
    client.cookies.clear()

    response = client.post(
        "/auth/login", json={"email": email, "password": "a-strong-password"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == email
    assert SESSION_COOKIE_NAME in response.cookies


def test_logging_in_with_the_wrong_password_is_rejected(client: TestClient) -> None:
    email = unique_email()
    client.post("/auth/register", json=register_payload(email=email))
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
    payload = register_payload()
    client.post("/auth/register", json=payload)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == payload["email"]
    assert response.json()["nickname"] == payload["nickname"]


def test_me_without_a_session_is_unauthorized(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_logging_out_clears_the_session(client: TestClient) -> None:
    client.post("/auth/register", json=register_payload())

    logout_response = client.post("/auth/logout")
    me_response = client.get("/auth/me")

    assert logout_response.status_code == 204
    assert me_response.status_code == 401


def test_one_users_session_cannot_read_another_users_data(client: TestClient) -> None:
    client.post("/auth/register", json=register_payload())
    first_user_id = client.get("/auth/me").json()["id"]
    client.cookies.clear()

    client.post("/auth/register", json=register_payload())
    second_user_id = client.get("/auth/me").json()["id"]

    assert first_user_id != second_user_id


def test_google_callback_creates_a_user_and_signs_in(client: TestClient) -> None:
    email = unique_email()
    given_name = unique_nickname()

    async def fake_authorize_access_token(request: object) -> dict:
        return {
            "userinfo": {
                "sub": f"google-{uuid.uuid4()}",
                "email": email,
                "given_name": given_name,
                "family_name": "Klimchuk",
            }
        }

    client.app.state.oauth.google.authorize_access_token = fake_authorize_access_token

    response = client.get("/auth/google/callback", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert SESSION_COOKIE_NAME in response.cookies

    me_response = client.get("/auth/me")
    assert me_response.json()["email"] == email
    assert me_response.json()["nickname"] == given_name
    assert me_response.json()["first_name"] == given_name
    assert me_response.json()["last_name"] == "Klimchuk"


def test_google_callback_links_an_existing_password_account(
    client: TestClient,
) -> None:
    payload = register_payload()
    client.post("/auth/register", json=payload)
    client.cookies.clear()

    async def fake_authorize_access_token(request: object) -> dict:
        return {
            "userinfo": {
                "sub": f"google-{uuid.uuid4()}",
                "email": payload["email"],
                "given_name": "Someone",
                "family_name": "Else",
                "email_verified": True,
            }
        }

    client.app.state.oauth.google.authorize_access_token = fake_authorize_access_token

    response = client.get("/auth/google/callback", follow_redirects=False)

    assert response.status_code in (302, 307)

    me_response = client.get("/auth/me")
    assert me_response.json()["email"] == payload["email"]
    assert me_response.json()["nickname"] == payload["nickname"]
    assert me_response.json()["first_name"] == payload["first_name"]


def test_google_callback_refuses_to_link_an_unverified_email(
    client: TestClient,
) -> None:
    payload = register_payload()
    client.post("/auth/register", json=payload)
    client.cookies.clear()

    async def fake_authorize_access_token(request: object) -> dict:
        return {
            "userinfo": {
                "sub": f"google-{uuid.uuid4()}",
                "email": payload["email"],
                "given_name": "Someone",
                "family_name": "Else",
                "email_verified": False,
            }
        }

    client.app.state.oauth.google.authorize_access_token = fake_authorize_access_token

    response = client.get("/auth/google/callback", follow_redirects=False)

    assert response.status_code == 401
    assert response.json()["code"] == "google_authentication_failed"
