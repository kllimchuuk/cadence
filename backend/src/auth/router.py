from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from auth.constants import SESSION_COOKIE_NAME
from auth.cookies import set_session_cookie
from auth.dependencies import (
    get_auth_service,
    get_current_user,
    get_google_oauth,
    get_settings,
)
from auth.oauth import exchange_google_token
from auth.schemas import LoginRequest, RegisterRequest, UserPublic
from auth.service import AuthService
from config import Settings
from users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=201)
async def register(
    payload: RegisterRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    app_settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublic:
    user, token = await auth_service.register(
        payload.email,
        payload.password,
        payload.first_name,
        payload.last_name,
        payload.nickname,
    )
    set_session_cookie(response, token, app_settings)
    return UserPublic.model_validate(user)


@router.post("/login", response_model=UserPublic)
async def login(
    payload: LoginRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    app_settings: Annotated[Settings, Depends(get_settings)],
) -> UserPublic:
    user, token = await auth_service.login(payload.email, payload.password)
    set_session_cookie(response, token, app_settings)
    return UserPublic.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.logout(request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserPublic)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserPublic:
    return UserPublic.model_validate(user)


@router.get("/google/login")
async def google_login(
    request: Request,
    google: Annotated[StarletteOAuth2App, Depends(get_google_oauth)],
) -> RedirectResponse:
    redirect_uri = request.url_for("google_callback")
    return await google.authorize_redirect(request, str(redirect_uri))


@router.get("/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    google: Annotated[StarletteOAuth2App, Depends(get_google_oauth)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    app_settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    token = await exchange_google_token(google, request)
    _, session_token = await auth_service.login_with_google_userinfo(token["userinfo"])

    redirect = RedirectResponse(url=app_settings.FRONTEND_URL)
    set_session_cookie(redirect, session_token, app_settings)
    return redirect
