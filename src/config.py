from typing import Any

from pydantic import BaseSettings, PostgresDsn, validator


class Settings(BaseSettings):
    ENV: str = "local"
    VERSION: str = "0.0.1"

    TIME_SYNC_SHOPS: str = "1"
    TIME_SYNC_MENU: str = "*"
    TIME_SYNC_STATUS: str = "*"

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8080

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "postgres"
    SQLALCHEMY_DATABASE_URI: PostgresDsn | str = ""

    EXTERNAL_HOST: str = ""
    RUBLE_CURRENCY_CODE: str = "F18FCABA-446C-4F90-9B0D-DCCFAD623C48"
    BONUS_CURRENCY_CODE: str = "1FAD32AC-6E2D-48B8-9DE2-154D34EDA26B"
    DISCOUNT_CURRENCY_CODE: str = "D2993C26-9894-4D46-918B-24AC1"
    DEFAULT_TIMEOUT: int = 20

    OPENTELEMETRY_AGENT_NAME: str = ""
    OPENTELEMETRY_COLLECTOR_ENDPOINT: str = ""
    OPENTELEMETRY_USERNAME: str = ""
    OPENTELEMETRY_PASSWORD: str = ""

    POS_GATEWAY_URL: str = "https://pos-gateway.starterapp.ru/api/"

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def check_db_connection(cls, v: str | None, values: dict[str, Any]) -> Any:
        if isinstance(v, str) and v:
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_HOST"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    @validator("REDIS_PORT", pre=True)
    def check_redis_port(cls, v: str | None, values: dict[str, Any]) -> Any:
        if isinstance(v, int) and v:
            return v

        return 6379

    class Config:
        env_file = "./.env"


settings = Settings()
