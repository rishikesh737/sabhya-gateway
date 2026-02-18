"""
Sabhya AI - Application Configuration with Validation

Uses Pydantic Settings for type-safe configuration from environment variables.
Validates critical settings at startup to prevent misconfigurations.
"""

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application configuration with type validation.

    All settings can be overridden via environment variables.
    """

    # =========================================================================
    # CORE
    # =========================================================================
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    APP_VERSION: str = "0.4.0"

    # =========================================================================
    # DATABASE
    # =========================================================================
    DATABASE_URL: str = "postgresql://sabhya:***REMOVED***@localhost:5432/sabhya_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    # =========================================================================
    # REDIS (Optional)
    # =========================================================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    SECRET_KEY: str = "***REMOVED***-key-change-in-production-minimum-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Legacy API key support (comma-separated)
    API_KEYS: str = "dev-key-1"
    LEGACY_AUTH_ENABLED: bool = True

    # =========================================================================
    # CORS & SECURITY
    # =========================================================================
    CORS_ORIGINS: str = "http://localhost:3000"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    # =========================================================================
    # PII DETECTION
    # =========================================================================
    PII_DETECTION_ENABLED: bool = True
    PII_BLOCKING_MODE: str = (
        "FLAG_ONLY"  # ALLOW_ALL, FLAG_ONLY, BLOCK_HIGH_RISK, BLOCK_ALL
    )
    PII_CONFIDENCE_THRESHOLD: float = 0.5
    PII_ANONYMIZE_LOGS: bool = True

    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    RATE_LIMIT_ENABLED: bool = True
    DEFAULT_RATE_LIMIT_PER_MINUTE: int = 50

    # =========================================================================
    # OLLAMA
    # =========================================================================
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODELS: str = "mistral:7b-instruct-q4_K_M"
    OLLAMA_TIMEOUT_SECONDS: int = 120

    # =========================================================================
    # CHROMA DB
    # =========================================================================
    CHROMA_DB_PATH: str = "./chroma_data"

    # =========================================================================
    # LOGGING
    # =========================================================================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text

    # =========================================================================
    # AUDIT
    # =========================================================================
    AUDIT_LOG_RETENTION_DAYS: int = 90
    AUDIT_HMAC_SECRET: str = "audit-secret-change-in-production-minimum-32-chars"

    # =========================================================================
    # MONITORING (Optional)
    # =========================================================================
    PROMETHEUS_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None

    # =========================================================================
    # VALIDATORS
    # =========================================================================

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate SECRET_KEY is secure enough for production."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    @field_validator("PII_BLOCKING_MODE")
    @classmethod
    def validate_pii_mode(cls, v: str) -> str:
        """Validate PII blocking mode."""
        valid_modes = ["ALLOW_ALL", "FLAG_ONLY", "BLOCK_HIGH_RISK", "BLOCK_ALL"]
        if v not in valid_modes:
            raise ValueError(f"PII_BLOCKING_MODE must be one of {valid_modes}")
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = ["development", "staging", "production"]
        if v not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v

    # =========================================================================
    # HELPERS
    # =========================================================================

    def get_cors_origins_list(self) -> List[str]:
        """Get CORS origins as list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def get_allowed_hosts_list(self) -> List[str]:
        """Get allowed hosts as list."""
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    def get_api_keys_list(self) -> List[str]:
        """Get API keys as list."""
        return [k.strip() for k in self.API_KEYS.split(",") if k.strip()]

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Allow extra env vars for backward compatibility


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


def validate_settings_on_startup() -> dict:
    """
    Validate all settings at application startup.

    Returns:
        {
            'valid': bool,
            'warnings': [list of warnings],
            'settings_loaded': [list of non-default settings]
        }
    """
    settings = get_settings()
    warnings = []

    # Check for default secrets in production
    if settings.is_production():
        if (
            "change" in settings.SECRET_KEY.lower()
            or "dev" in settings.SECRET_KEY.lower()
        ):
            warnings.append("SECRET_KEY appears to be a default value in production!")

        if (
            "change" in settings.AUDIT_HMAC_SECRET.lower()
            or "dev" in settings.AUDIT_HMAC_SECRET.lower()
        ):
            warnings.append(
                "AUDIT_HMAC_SECRET appears to be a default value in production!"
            )

        if "*" in settings.CORS_ORIGINS:
            warnings.append("CORS allows all origins in production!")

        if settings.DEBUG:
            warnings.append("DEBUG mode is enabled in production!")

    # Log settings (sanitized)
    logger.info("=" * 60)
    logger.info("SABHYA AI CONFIGURATION")
    logger.info("=" * 60)
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug: {settings.DEBUG}")
    logger.info(
        f"PII Detection: {settings.PII_DETECTION_ENABLED} ({settings.PII_BLOCKING_MODE})"
    )
    logger.info(
        f"Rate Limiting: {settings.RATE_LIMIT_ENABLED} ({settings.DEFAULT_RATE_LIMIT_PER_MINUTE}/min)"
    )
    logger.info(f"Ollama: {settings.OLLAMA_BASE_URL}")
    logger.info(f"Legacy Auth: {settings.LEGACY_AUTH_ENABLED}")
    logger.info("=" * 60)

    if warnings:
        for warning in warnings:
            logger.warning(f"⚠️  {warning}")

    return {
        "valid": len(warnings) == 0 or not settings.is_production(),
        "warnings": warnings,
        "environment": settings.ENVIRONMENT,
    }


# Convenience export
settings = get_settings()
