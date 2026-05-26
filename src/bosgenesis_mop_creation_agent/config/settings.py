import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SECRET_KEYS = ("password", "secret", "token", "key", "credential", "connection_string")


class AgentSettings(BaseModel):
    name: str = "bosgenesis-mop-creation-agent"
    mode: str = "on_demand"
    source_namespace: str = "bosgenesis"
    local_storage_enabled: bool = True
    local_storage_path: str = "/data/mops"
    default_generation_mode: str = "platform-only"
    public_repositories_only: bool = True


class ApiSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "json"


class EndpointSettings(BaseModel):
    enabled: bool = True
    endpoint: str | None = None


class McpSettings(BaseModel):
    k8s_inspector: EndpointSettings = Field(default_factory=EndpointSettings)
    helm_manager: EndpointSettings = Field(default_factory=EndpointSettings)
    data_ingestion_agent: EndpointSettings = Field(default_factory=EndpointSettings)


class QdrantRetrievalSettings(BaseModel):
    enabled: bool = True
    mode: str = "read_only"
    endpoint: str | None = None
    collection: str = "mop_installation_notes"
    top_k: int = 5
    min_score: float = 0.72
    ingestion_owned_by: str = "separate-agent"


class RetrievalSettings(BaseModel):
    qdrant: QdrantRetrievalSettings = Field(default_factory=QdrantRetrievalSettings)


class ObservabilitySettings(BaseModel):
    langfuse_enabled: bool = True
    signoz_enabled: bool = True
    otlp_endpoint: str | None = None


class LlmSettings(BaseModel):
    standalone_enabled: bool = True
    framework: str = "langgraph-langchain"
    default_model: str = "gpt-4.1-mini"


class Settings(BaseModel):
    agent: AgentSettings = Field(default_factory=AgentSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)

    def redacted_dict(self) -> dict[str, Any]:
        return redact(self.model_dump())


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            if any(secret_key in key.lower() for secret_key in SECRET_KEYS):
                redacted[key] = "***REDACTED***" if nested else nested
            else:
                redacted[key] = redact(nested)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and any(marker in value.lower() for marker in SECRET_KEYS):
        return "***REDACTED***"
    return value



def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path or os.getenv("BOSGENESIS_MOP_CONFIG_PATH", "config/settings.yaml"))
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    settings = Settings.model_validate(raw)
    return _apply_env_overrides(settings)


def _apply_env_overrides(settings: Settings) -> Settings:
    update: dict[str, Any] = settings.model_dump()

    env_map = {
        "BOSGENESIS_MOP_AGENT_NAME": ("agent", "name"),
        "BOSGENESIS_MOP_SOURCE_NAMESPACE": ("agent", "source_namespace"),
        "BOSGENESIS_MOP_LOCAL_STORAGE_PATH": ("agent", "local_storage_path"),
        "BOSGENESIS_MOP_API_HOST": ("api", "host"),
        "BOSGENESIS_MOP_API_PORT": ("api", "port"),
        "BOSGENESIS_MOP_LOG_LEVEL": ("logging", "level"),
        "BOSGENESIS_MOP_LOG_FORMAT": ("logging", "format"),
    }
    for env_name, path in env_map.items():
        env_value = os.getenv(env_name)
        if env_value is None:
            continue
        parent = update[path[0]]
        value: Any = int(env_value) if env_name.endswith("_PORT") else env_value
        parent[path[1]] = value

    return Settings.model_validate(update)
