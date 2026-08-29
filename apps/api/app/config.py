from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "revampradar-api"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://revampradar:revampradar@localhost:5433/revampradar"
    cors_origins: str = (
        "http://localhost:1420,http://localhost:5173,http://127.0.0.1:1420,"
        "tauri://localhost,http://tauri.localhost"
    )
    screenshot_dir: str = str(_REPO_ROOT / "data" / "screenshots")
    request_timeout_seconds: float = 15.0
    browser_timeout_ms: int = 20000
    scanner_user_agent: str = "RevampRadar/1.0 (+https://revampradar.local)"
    pagespeed_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    discovery_timeout_seconds: float = 60.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
