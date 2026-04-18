from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://vintiz:vintiz@localhost:5432/vintiz"

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # AI
    ANTHROPIC_API_KEY: str | None = None

    # CORS - comma-separated string, parsed via property
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # SEO / Analytics
    PUBLIC_SITE_URL: str = "https://vintiz.fr"
    GA_MEASUREMENT_ID: str | None = None
    GOOGLE_SITE_VERIFICATION: str | None = None
    GSC_PROPERTY: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.CORS_ORIGINS.split(",") if s.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
