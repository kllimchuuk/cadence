from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cadence"
    TEST_DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cadence_test"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


settings = Settings()
