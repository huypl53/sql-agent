from typing import Literal
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource,
)
from pydantic import ConfigDict, Field
import os
from dotenv import load_dotenv

load_dotenv(override=True)


class _Database(BaseSettings):
    dialect: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="mysql",
        alias="DB_DIALECT",
    )
    conn: str = Field(
        default="sqlite:///Chinook.db",
        alias="DB_CONN",
    )


class _LLM(BaseSettings):
    provider: str = Field(
        default="openai",
        alias="LLM_MODEL_PROVIDER",
    )
    model: str = Field(
        default="gpt-4o-mini",
        alias="LLM_MODEL",
    )


class _Logging(BaseSettings):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        alias="LOG_LEVEL",
    )

    log_dir: str = Field(
        default="./logs/",
        alias="LOG_DIR",
    )
    max_bytes: int = Field(
        default=1048576,
        alias="LOG_MAX_BYTES",
    )
    backup_count: int = Field(
        default=3,
        alias="LOG_BACKUP_COUNT",
    )


class Settings(BaseSettings):
    model_config = ConfigDict(extra="allow")
    schema_path: str = Field(
        alias="SCHEMA_PATH",
    )
    logging: _Logging = _Logging()
    database: _Database = _Database()
    llm: _LLM = _LLM()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: DotEnvSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Customize the order and types of settings sources.

        The order here determines precedence:
        - init_settings: Values passed directly to the constructor (highest precedence)
        - YamlConfigSettingsSource: Values from config.yaml
        - dotenv_settings: Values from .env file
        - env_settings: Values from environment variables
        """
        return (
            init_settings,  # 1. Constructor arguments
            YamlConfigSettingsSource(
                settings_cls, "config.yaml"
            ),  # 2. Our custom YAML source
            dotenv_settings,  # 3. .env file
            env_settings,  # 4. Environment variables
        )


settings = Settings()
if not os.path.exists(settings.logging.log_dir):
    os.makedirs(settings.logging.log_dir)

if __name__ == "__main__":
    print(settings.model_dump_json(indent=2))


def get_app_config():
    return settings
