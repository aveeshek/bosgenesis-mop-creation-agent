import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SECRET_KEYS = ("password", "secret", "token", "key", "credential", "connection_string", "dsn")


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
    host_header: str | None = None
    timeout_seconds: float = 30


class K8sInspectorSettings(EndpointSettings):
    detail_enrichment_kinds: list[str] = Field(
        default_factory=lambda: [
            "ConfigMap",
            "Service",
            "Deployment",
            "StatefulSet",
            "DaemonSet",
            "Job",
            "CronJob",
            "PersistentVolumeClaim",
            "Ingress",
        ]
    )


class McpSettings(BaseModel):
    k8s_inspector: K8sInspectorSettings = Field(default_factory=K8sInspectorSettings)
    helm_manager: EndpointSettings = Field(default_factory=EndpointSettings)
    data_ingestion_agent: EndpointSettings = Field(default_factory=EndpointSettings)


class ArtifactPreviewSettings(BaseModel):
    enabled: bool = True
    max_bytes: int = 262144
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".json", ".md", ".yaml", ".yml"]
    )


class FeatureSettings(BaseModel):
    artifact_preview: ArtifactPreviewSettings = Field(default_factory=ArtifactPreviewSettings)


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


class InventoryPostgresSettings(BaseModel):
    enabled: bool = True
    dsn: str | None = None
    schema_name: str = "k8s_ingestion"


class InventoryClickHouseSettings(BaseModel):
    enabled: bool = True
    host: str = "clickhouse.bosgenesis.svc.cluster.local"
    port: int = 8123
    user: str = "bosgenesis"
    password: str | None = None
    database: str = "bosgenesis_k8s_ingestion"


class InventorySettings(BaseModel):
    postgres: InventoryPostgresSettings = Field(default_factory=InventoryPostgresSettings)
    clickhouse: InventoryClickHouseSettings = Field(default_factory=InventoryClickHouseSettings)


class ObservabilitySettings(BaseModel):
    langfuse_enabled: bool = True
    signoz_enabled: bool = True
    otlp_endpoint: str | None = None


class LlmModelProfile(BaseModel):
    provider: str = "azure_openai"
    model: str | None = None
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    azure_api_version: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    enabled: bool = True


class LlmSettings(BaseModel):
    standalone_enabled: bool = True
    framework: str = "langgraph-langchain"
    default_model: str = "gemma4:26b"
    repair_suggestions_enabled: bool = False
    provider: str = "ollama"
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    azure_api_version: str = "2024-12-01-preview"
    temperature: float = 0.2
    max_tokens: int = 800
    minimum_confidence: float = 0.85
    model_profiles: dict[str, LlmModelProfile] = Field(
        default_factory=lambda: {
            "gemma4:26b": LlmModelProfile(
                provider="ollama",
                model="gemma4:26b",
                base_url="http://ollama.bosgenesis.svc.cluster.local:11434",
                max_tokens=2048,
            ),
            "gpt-4.1-mini": LlmModelProfile(
                provider="azure_openai",
                azure_deployment="bos-trainium-sigma-gpt-4.1-mini",
                azure_api_version="2024-12-01-preview",
            ),
            "gpt-5": LlmModelProfile(
                provider="azure_openai",
                azure_deployment="gpt-5",
                azure_api_version="2024-12-01-preview",
            ),
            "gemma4": LlmModelProfile(
                provider="ollama",
                model="gemma4:26b",
                base_url="http://ollama.bosgenesis.svc.cluster.local:11434",
                max_tokens=2048,
            ),
            "llama70b": LlmModelProfile(
                provider="ollama",
                model="llama3.3:70b",
                base_url="http://ollama-llama70b.bosgenesis.svc.cluster.local:11434",
            ),
        }
    )

    def active_profile(self) -> LlmModelProfile:
        profile = self.model_profiles.get(self.default_model)
        if profile is None:
            return LlmModelProfile(
                provider=self.provider,
                model=self.default_model,
                azure_endpoint=self.azure_endpoint,
                azure_deployment=self.azure_deployment,
                azure_api_version=self.azure_api_version,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        return profile.model_copy(
            update={
                "azure_endpoint": profile.azure_endpoint or self.azure_endpoint,
                "azure_api_version": profile.azure_api_version or self.azure_api_version,
                "temperature": profile.temperature
                if profile.temperature is not None
                else self.temperature,
                "max_tokens": profile.max_tokens if profile.max_tokens is not None else self.max_tokens,
            }
        )


class Settings(BaseModel):
    agent: AgentSettings = Field(default_factory=AgentSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)
    inventory: InventorySettings = Field(default_factory=InventorySettings)
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
        "POSTGRES_ENABLED": ("inventory", "postgres", "enabled"),
        "POSTGRES_DSN": ("inventory", "postgres", "dsn"),
        "POSTGRES_SCHEMA": ("inventory", "postgres", "schema_name"),
        "CLICKHOUSE_ENABLED": ("inventory", "clickhouse", "enabled"),
        "CLICKHOUSE_HOST": ("inventory", "clickhouse", "host"),
        "CLICKHOUSE_PORT": ("inventory", "clickhouse", "port"),
        "CLICKHOUSE_USER": ("inventory", "clickhouse", "user"),
        "CLICKHOUSE_PASSWORD": ("inventory", "clickhouse", "password"),
        "CLICKHOUSE_DATABASE": ("inventory", "clickhouse", "database"),
        "LLM_REPAIR_SUGGESTIONS_ENABLED": ("llm", "repair_suggestions_enabled"),
        "LLM_DEFAULT_MODEL": ("llm", "default_model"),
        "LLM_PROVIDER": ("llm", "provider"),
        "AZURE_OPENAI_ENDPOINT": ("llm", "azure_endpoint"),
        "OPENAI_DEPLOYMENT": ("llm", "azure_deployment"),
        "OPENAI_API_VERSION": ("llm", "azure_api_version"),
        "OLLAMA_BASE_URL": ("llm", "model_profiles", "gemma4:26b", "base_url"),
        "OLLAMA_MODEL": ("llm", "model_profiles", "gemma4:26b", "model"),
        "OLLAMA_GEMMA4_BASE_URL": ("llm", "model_profiles", "gemma4", "base_url"),
        "OLLAMA_GEMMA4_MODEL": ("llm", "model_profiles", "gemma4", "model"),
        "OLLAMA_LLAMA70B_BASE_URL": ("llm", "model_profiles", "llama70b", "base_url"),
        "OLLAMA_LLAMA70B_MODEL": ("llm", "model_profiles", "llama70b", "model"),
    }
    for env_name, path in env_map.items():
        env_value = os.getenv(env_name)
        if env_value is None:
            continue
        parent = update[path[0]]
        for nested_key in path[1:-1]:
            parent = parent[nested_key]
        value: Any
        if env_name.endswith("_PORT"):
            value = int(env_value)
        elif env_name.endswith("_ENABLED"):
            value = env_value.lower() in {"1", "true", "yes", "on"}
        else:
            value = env_value
        parent[path[-1]] = value

    return Settings.model_validate(update)
