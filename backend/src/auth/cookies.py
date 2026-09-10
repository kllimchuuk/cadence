from fastapi import Response

from auth.constants import SESSION_COOKIE_NAME, SESSION_TTL
from config import Settings


def set_session_cookie(response: Response, token: str, app_settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=app_settings.SECURE_COOKIES,
        samesite="lax",
        path="/",
    )
