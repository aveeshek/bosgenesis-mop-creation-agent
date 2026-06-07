# Runtime Config Specification

## Intent

`config/` defines runtime settings, safe defaults, environment loading, and redacted effective configuration output.

## Configuration groups

- Agent identity and v1 scope.
- Runtime invocation mode.
- Generation mode defaults.
- MCP dependency endpoints.
- Snapshot store settings.
- Local artifact storage.
- Optional persistence stores.
- Read-only Qdrant prior-reference retrieval settings.
- LLM, LangGraph, and LangChain settings.
- LangMem and memory backend settings.
- Observability settings.
- Security and redaction policy.

## Required defaults

```text
agent.name = bosgenesis-mop-creation-agent
agent.mode = on_demand
agent.source_namespace = bosgenesis
release.values_schema_version = phase15.rc.v1
release.release_candidate = phase15-rc1
release.app_version = 0.1.0
release.docs_version = phase15
agent.public_repositories_only = true
agent.default_generation_mode = platform-only
local_storage.enabled = true
features.artifact_preview.allowed_extensions = [.json, .md, .yaml, .yml]
features.artifact_preview.download_extensions = [.json, .md, .yaml, .yml, .pdf]
llm.default_model = gemma4:26b
llm.reasoning_enabled = false in package defaults, true in deploy configuration when Phase 10 is enabled
llm.repair_suggestions_enabled = false
llm.provider = ollama
llm.azure_endpoint = optional Azure OpenAI endpoint
llm.azure_deployment = optional Azure OpenAI deployment name
llm.azure_api_version = 2024-12-01-preview
llm.minimum_confidence = 0.85
llm.model_profiles.gemma4:26b.provider = ollama
llm.model_profiles.gpt-4.1-mini.provider = azure_openai
llm.model_profiles.gpt-5.provider = azure_openai
llm.model_profiles.gemma4.provider = ollama
llm.model_profiles.llama70b.provider = ollama
memory.enabled = false
memory.langmem_enabled = true
memory.redis.enabled = true
memory.pgvector.enabled = true
memory.qdrant.enabled = false
memory.letta.enabled = false
observability.langfuse_enabled = true
observability.langfuse_endpoint = http://langfuse-web.bosgenesis.svc.cluster.local:3000
observability.langfuse_public_key = optional secret-provided key
observability.langfuse_secret_key = optional secret-provided key
observability.signoz_enabled = true
observability.otlp_endpoint = http://signoz-otel-collector.signoz.svc.cluster.local:4317
observability.audit_enabled = true
observability.phase_metrics_enabled = true
observability.warning_taxonomy_enabled = true
```

`agent.source_namespace` is the configured default source namespace. Runtime
namespace switching may override the active source namespace in memory for the
current process, but it must not mutate the static config or Helm values.

`memory.enabled` controls the Phase 11 agentic memory layer. Memory is disabled
by default. When enabled, the in-process LangMem-shaped adapter is the first/cache
layer. Redis is the implemented durable short-term memory backend using
namespace-scoped list keys. PostgreSQL/pgvector is the implemented durable
episodic memory backend using `MEMORY_PGVECTOR_DSN` and the configured memory
table. Qdrant/Letta remain disabled future memory placeholders until their
durable wiring is explicitly enabled.

`observability.*` settings control Phase 13 audit hardening. Audit, phase latency metrics, and warning taxonomy are enabled by default. SigNoz/OpenTelemetry exports phase spans to the configured OTLP collector when exporter packages are available. Langfuse emits redacted reasoning metadata when endpoint and public/secret keys are configured. Both sinks must degrade to sink status metadata when SDK/runtime wiring or credentials are unavailable. The lab Langfuse service endpoint is `http://langfuse-web.bosgenesis.svc.cluster.local:3000`; the SigNoz OTLP endpoint is `http://signoz-otel-collector.signoz.svc.cluster.local:4317`.

Credential update procedures for PostgreSQL, ClickHouse, Redis, Qdrant,
Langfuse, SigNoz/OpenTelemetry, MCP endpoints, and LLM endpoints are maintained
in `docs/CREDENTIALS.md`. Tracked config must keep placeholder or non-secret
values only.

`llm.default_model` selects the active profile. Switching among supported models
should require only a config value change, for example `gemma4:26b`, `gpt-4.1-mini`,
`gpt-5`, `gemma4`, or `llama70b`.

## Safe output

Effective configuration exposed through REST or MCP must redact:

- credentials;
- API keys;
- tokens;
- passwords;
- connection strings with credentials;
- secret-like values.

## Validation

Configuration validation must reject settings that violate v1 boundaries unless a future accepted spec explicitly expands scope.
