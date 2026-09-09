from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth.constants import SESSION_COOKIE_NAME
from auth.exceptions import NotAuthenticatedError
from auth.repository import UserSessionRepository
from auth.service import AuthService
from core.database import get_db
from users.models import User
from users.repository import UserRepositoryImpl


def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(UserRepositoryImpl(session), UserSessionRepository(session))


async def get_current_user(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = await auth_service.authenticate(token) if token else None

    if user is None:
        raise NotAuthenticatedError()

    return user
