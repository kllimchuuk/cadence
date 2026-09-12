from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import Depends, Request

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


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_current_user(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = await auth_service.authenticate(token) if token else None

    if user is None:
        raise NotAuthenticatedError()

    return user
