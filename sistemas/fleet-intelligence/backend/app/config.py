"""Application configuration loaded from environment variables.

Variaveis carregadas do .env central em C:\\env\\.env (host Windows).
No container Linux, o docker-compose injeta as variaveis via env_file,
entao pydantic-settings as le direto do process.env sem precisar do
arquivo fisico.
"""
import os
import platform
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_file_path() -> str:
    """Path do .env central: C:\\env\\.env no Windows, /app/.env no container Linux."""
    if platform.system() == "Windows":
        return r"C:\env\.env"
    # Dentro do container Linux, o docker-compose monta em /app/.env.
    return "/app/.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file_path(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Fleet Intelligence"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "fleet_intelligence"

    # Auth (JWT proprio do Fleet Intelligence)
    JWT_SECRET_KEY: str = "change-me-in-production-please-very-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    # SSO — Command Center (login unificado)
    PORTAL_JWT_SECRET: str = ""
    COMMAND_CENTER_PORT: int = 4001

    # SMTP (Gmail / Google Workspace) — prefixadas FI_ para nao conflitar
    # com SMTP_* do Portal (que usa Office365/OAuth Azure).
    FI_SMTP_HOST: str = "smtp.gmail.com"
    FI_SMTP_PORT: int = 587
    FI_SMTP_USER: str = ""
    FI_SMTP_PASSWORD: str = ""
    FI_SMTP_FROM_NAME: str = "Fleet Intelligence"
    FI_SMTP_FROM_EMAIL: str = ""
    FI_ADMIN_EMAIL: str = "henrique.albuquerque@venezanet.com"

    # Frontend URL (para links nos emails)
    FRONTEND_URL: str = "http://192.168.0.106:8087"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://192.168.0.106,http://192.168.0.106:8087"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
