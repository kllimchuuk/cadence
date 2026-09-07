from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from auth.constants import SESSION_COOKIE_NAME, SESSION_TTL
from auth.dependencies import get_auth_service, get_current_user
from auth.service import AuthService
from users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserPublic(BaseModel):
    id: str
    email: str


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserPublic, status_code=201)
async def register(
    payload: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    user, token = await auth_service.register(payload.email, payload.password)
    _set_session_cookie(response, token)
    return UserPublic(id=str(user.id), email=user.email)


@router.post("/login", response_model=UserPublic)
async def login(
    payload: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    user, token = await auth_service.login(payload.email, payload.password)
    _set_session_cookie(response, token)
    return UserPublic(id=str(user.id), email=user.email)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        await auth_service.logout(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic(id=str(user.id), email=user.email)
