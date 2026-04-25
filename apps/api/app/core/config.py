import logging
import os
import secrets

from pydantic_settings import BaseSettings

logger = logging.getLogger("vintiz")

# Sentinel value indicating an unset SECRET_KEY (refused in production).
_INSECURE_DEFAULT_KEY = "change-me-in-production-use-openssl-rand-hex-32"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment: 'development' | 'staging' | 'production'
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://vintiz:vintiz@localhost:5432/vintiz"

    # Auth / JWT
    SECRET_KEY: str = _INSECURE_DEFAULT_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Rate limiting
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # AI
    ANTHROPIC_API_KEY: str | None = None

    # CORS - comma-separated string, parsed via property
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # SEO / Analytics
    PUBLIC_SITE_URL: str = "https://vintiz.fr"
    GA_MEASUREMENT_ID: str | None = None
    GOOGLE_SITE_VERIFICATION: str | None = None
    GSC_PROPERTY: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.CORS_ORIGINS.split(",") if s.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


def _validate_secret_key() -> None:
    """Refuse to boot in production with an insecure / default SECRET_KEY.

    In non-production environments we generate a random key on the fly and warn,
    so developers don't accidentally rely on a hardcoded value.
    """
    if settings.SECRET_KEY in {"", _INSECURE_DEFAULT_KEY}:
        if settings.is_production:
            raise RuntimeError(
                "SECRET_KEY is unset or uses the insecure default. "
                "Set SECRET_KEY in your environment "
                "(generate via: python -c 'import secrets; print(secrets.token_hex(32))')."
            )
        # Auto-generate ephemeral key for dev so tokens don't survive restarts
        # but at least aren't predictable.
        ephemeral = os.environ.get("VINTIZ_DEV_EPHEMERAL_KEY")
        if not ephemeral:
            ephemeral = secrets.token_hex(32)
            os.environ["VINTIZ_DEV_EPHEMERAL_KEY"] = ephemeral
        settings.SECRET_KEY = ephemeral
        logger.warning(
            "SECRET_KEY not set — generated an ephemeral key for development. "
            "DO NOT use this in production."
        )
    elif len(settings.SECRET_KEY) < 32:
        logger.warning(
            "SECRET_KEY is shorter than 32 characters; consider rotating to a longer secret."
        )


_validate_secret_key()
