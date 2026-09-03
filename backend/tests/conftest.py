from pathlib import Path

from dotenv import load_dotenv


def pytest_configure() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
