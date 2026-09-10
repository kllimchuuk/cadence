from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    APP_HOST: str
    APP_PORT: int
    CORS_ORIGINS: str
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    SECRET_KEY: str
    SECURE_COOKIES: bool
    FRONTEND_URL: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_SERVER_METADATA_URL: str

    @model_validator(mode="after")
    def _require_a_secret_key(self) -> "Settings":
        if not self.SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set — it signs the OAuth state cookie."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


settings = Settings()
