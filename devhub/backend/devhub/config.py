"""Explicit environment contract; secrets never belong in browser assets."""

from dataclasses import dataclass, field
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    frontend_dist: str = field(default_factory=lambda: os.getenv("FRONTEND_DIST", ""))
    process_role: str = field(default_factory=lambda: os.getenv("PROCESS_ROLE", "api"))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql+psycopg://devhub:devhub@localhost:5432/devhub"
        )
    )
    app_origin: str = field(
        default_factory=lambda: os.getenv("APP_ORIGIN", "http://localhost:8000").rstrip("/")
    )
    dev_auth_enabled: bool = field(
        default_factory=lambda: os.getenv("DEV_AUTH_ENABLED", "false").lower() == "true"
    )
    github_client_id: str = field(default_factory=lambda: os.getenv("GITHUB_CLIENT_ID", ""))
    github_client_secret: str = field(
        default_factory=lambda: os.getenv("GITHUB_CLIENT_SECRET", ""), repr=False
    )
    github_app_id: str = field(default_factory=lambda: os.getenv("GITHUB_APP_ID", ""))
    github_private_key: str = field(
        default_factory=lambda: os.getenv("GITHUB_PRIVATE_KEY", "").replace("\\n", "\n")
    )
    github_webhook_secret: str = field(default_factory=lambda: os.getenv("GITHUB_WEBHOOK_SECRET", ""))
    github_installation_bindings: str = field(
        default_factory=lambda: os.getenv("GITHUB_INSTALLATION_BINDINGS", "")
    )
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", ""))

    def validate(self) -> None:
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        origin = urlparse(self.app_origin)
        if (
            origin.scheme not in {"http", "https"}
            or not origin.hostname
            or origin.path
            or origin.query
            or origin.fragment
            or origin.username
        ):
            raise ValueError("APP_ORIGIN must be an exact HTTP(S) origin without a path")
        if self.process_role not in {"api", "worker", "migration"}:
            raise ValueError("Invalid PROCESS_ROLE")
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test, or production")
        if self.environment == "production":
            if self.dev_auth_enabled:
                raise ValueError("Development authentication is forbidden in production")
            if origin.scheme != "https":
                raise ValueError("Production APP_ORIGIN must use HTTPS")
            # Missing OAuth credentials leave sign-in unavailable; never fall back to dev auth.


settings = Settings()
settings.validate()
