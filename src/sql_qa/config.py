from typing import Any, Dict, List, Literal, Optional, Union
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
from shared.logger import TurnLogger

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


class LlmConfig(BaseSettings):
    model_config = ConfigDict(extra="allow")

    model: str = Field(
        default="google_genai:gemini-2.0-flash",
    )


class GenerationConfig(BaseSettings):
    model_config = ConfigDict(extra="allow")

    prompt_type: str = Field()
    query_validation_kwargs: LlmConfig
    generation_kwargs: LlmConfig
    query_fixer_kwargs: LlmConfig


class MCPConfig(BaseSettings):
    transport: Literal["sse", "streamable_http", "stdio"] = Field(
        default="sse",
    )
    server_name: Literal["mcp-server-chart", "mcp-server-text2sql"] = Field(
        default="mcp-server-chart",
        description="Name of the MCP server",
    )

    # SSE or streamable_http
    port: Optional[int] = Field(
        default=None,
        description="Port of the MCP server if mode is sse or stream",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL of the MCP server if mode is sse or stream",
    )

    # stdio
    command: Optional[str] = Field(
        default=None,
        description="Command to start the MCP server if mode is stdio",
    )
    args: Optional[List[str]] = Field(
        default=None,
        description="Arguments to start the MCP server if mode is stdio",
    )

    def to_dict(self) -> Dict[str, Any]:
        if self.transport == "sse":
            return {
                self.server_name: {
                    "url": self.url,
                    "transport": self.transport,
                }
            }
        elif self.transport == "streamable_http":
            return {
                self.server_name: {
                    "url": self.url,
                    "transport": self.transport,
                }
            }
        elif self.transport == "stdio":
            return {
                self.server_name: {
                    "command": self.command,
                    "args": self.args,
                    "transport": self.transport,
                }
            }
        else:
            raise ValueError(f"Invalid transport: {self.transport}")


class Settings(BaseSettings):
    model_config = ConfigDict(extra="allow")

    mode: Literal["dev", "prod", "benchmark"] = Field(
        default="dev",
        alias="MODE",
    )

    schema_path: str = Field(
        alias="SCHEMA_PATH",
    )
    database: _Database = _Database()
    logging: _Logging = _Logging()
    llm: _LLM = _LLM()
    candidate_generations: List[GenerationConfig]

    result_enhancement: LlmConfig
    schema_linking: LlmConfig
    merger: LlmConfig
    turn_log_file: str = Field(
        default="./logs/turn_log.csv",
        alias="TURN_LOG_FILE",
    )

    # MCP setup
    mcp_servers: List[MCPConfig] = Field(
        default=[],
        description="List of MCP servers",
    )

    orchestrator: LlmConfig = LlmConfig()

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

turn_logger = TurnLogger(settings.turn_log_file)

if __name__ == "__main__":
    print(settings.model_dump_json(indent=2))


def get_app_config():
    return settings
