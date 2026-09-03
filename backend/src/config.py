from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"


settings = Settings()

CORS_ORIGINS = [
    origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
]
