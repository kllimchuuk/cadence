from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import Request

from auth.exceptions import GoogleAuthenticationError
from config import Settings


def build_google_oauth(settings: Settings) -> OAuth:
    oauth = OAuth()
    oauth.register(
        name="google",
        server_metadata_url=settings.GOOGLE_SERVER_METADATA_URL,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


async def exchange_google_token(
    google: StarletteOAuth2App, request: Request
) -> dict[str, object]:
    try:
        return await google.authorize_access_token(request)
    except OAuthError as error:
        raise GoogleAuthenticationError() from error
