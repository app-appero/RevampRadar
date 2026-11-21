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
    # Vuoto = Chromium installato da Playwright. Utile se la versione di Playwright non coincide.
    browser_executable_path: str = ""
    # Link interni della home controllati per i link rotti (0 = controllo disattivato).
    broken_links_max: int = 10
    scanner_user_agent: str = "RevampRadar/1.0 (+https://revampradar.local)"
    pagespeed_api_key: str = ""
    ai_provider: str = "claude"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 90.0
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_version: str = "2023-06-01"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    # Server di riserva provati in ordine se il precedente è irraggiungibile, in timeout o in errore.
    overpass_urls: str = (
        "https://overpass-api.de/api/interpreter,"
        "https://overpass.kumi.systems/api/interpreter,"
        "https://overpass.private.coffee/api/interpreter,"
        "https://lz4.overpass-api.de/api/interpreter"
    )
    discovery_timeout_seconds: float = 60.0
    # Timeout Overpass su una provincia: ricerca per gruppi di comuni (admin_level 8).
    overpass_comuni_group_size: int = 12
    # Tentativi per query (timeout, server sovraccarico, rete), con attesa crescente tra l'uno e l'altro.
    overpass_retry_attempts: int = 3
    overpass_retry_backoff_seconds: float = 5.0
    # Richieste Overpass contemporanee dall'intero processo: i server pubblici ne ammettono ~2 per IP,
    # oltre rispondono 429. Più discovery lanciate insieme si mettono in fila invece di fallire.
    overpass_max_concurrency: int = 2
    # Una discovery "running"/"queued" senza avanzamenti da più minuti di così diventa "failed".
    discovery_stale_minutes: int = 20
    bulk_scan_concurrency: int = 2
    bulk_scan_max_attempts: int = 2
    basic_auth_user: str = ""
    basic_auth_password: str = ""
    # Dopo un accesso Basic valido il browser riceve un cookie di sessione firmato valido per
    # queste ore (0 = disattivato): le fetch delle pagine restano autenticate anche quando il
    # browser dimentica le credenziali Basic.
    basic_auth_session_hours: float = 168

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
