from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # application
    app_name: str = Field(default="ServiceDesk", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # http
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    workers: int = Field(default=1, alias="WORKERS")

    # database
    database_url: str = Field(default="sqlite:///./servicedesk.db", alias="DATABASE_URL")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    # security
    secret_key: str = Field(default="dev-secret-change-me", alias="SECRET_KEY")
    token_ttl_hours: int = Field(default=12, alias="TOKEN_TTL_HOURS")
    pbkdf2_iterations: int = Field(default=200_000, alias="PBKDF2_ITERATIONS")

    # seed
    seed_passwords: bool = Field(default=False, alias="SEED_PASSWORDS")
    seed_client_password: str = Field(default="client123", alias="SEED_CLIENT_PASSWORD")
    seed_operator_password: str = Field(default="operator123", alias="SEED_OPERATOR_PASSWORD")

    # health
    health_check_db: bool = Field(default=True, alias="HEALTH_CHECK_DB")


@lru_cache
def get_settings() -> Settings:
    return Settings()
