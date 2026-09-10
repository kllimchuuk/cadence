from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth.constants import SESSION_COOKIE_NAME
from auth.exceptions import NotAuthenticatedError
from auth.repository import UserSessionRepository
from auth.service import AuthService
from config import Settings
from core.database import get_db
from users.models import User
from users.repository import UserRepositoryImpl


def get_auth_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(UserRepositoryImpl(session), UserSessionRepository(session))


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
