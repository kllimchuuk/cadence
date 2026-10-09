from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import Depends, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import HTTPConnection

from auth.constants import SESSION_COOKIE_NAME
from auth.exceptions import NotAuthenticatedError
from auth.repository import (
    UserSessionRepository,
    UserSessionRepositoryImpl,
    get_user_session_repository,
)
from auth.service import AuthService
from config import Settings
from core.database import get_session_factory
from users.models import User
from users.repository import UserRepository, UserRepositoryImpl, get_user_repository


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


async def get_current_user(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = await auth_service.authenticate(token) if token else None

    if user is None:
        raise NotAuthenticatedError()

    return user


async def get_websocket_user(
    websocket: WebSocket,
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> User | None:
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    async with session_factory() as session:
        auth_service = AuthService(
            user_repository=UserRepositoryImpl(session),
            session_repository=UserSessionRepositoryImpl(session),
        )
        user = await auth_service.authenticate(token)
        await session.commit()

    return user
