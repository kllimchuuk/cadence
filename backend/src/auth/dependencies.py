from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from auth.constants import SESSION_COOKIE_NAME
from auth.exceptions import NotAuthenticatedError
from auth.repository import UserSessionRepository, get_user_session_repository
from auth.service import AuthService
from config import Settings
from users.models import User
from users.repository import UserRepository, get_user_repository


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    session_repository: Annotated[
        UserSessionRepository, Depends(get_user_session_repository)
    ],
) -> AuthService:
    return AuthService(
        user_repository=user_repository, session_repository=session_repository
    )


def get_google_oauth(request: Request) -> StarletteOAuth2App:
    return request.app.state.oauth.google


def get_settings(conn: HTTPConnection) -> Settings:
    return conn.app.state.settings


async def get_optional_current_user(
    conn: HTTPConnection,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User | None:
    token = conn.cookies.get(SESSION_COOKIE_NAME)
    return await auth_service.authenticate(token) if token else None


async def get_current_user(
    user: Annotated[User | None, Depends(get_optional_current_user)],
) -> User:
    if user is None:
        raise NotAuthenticatedError()

    return user
