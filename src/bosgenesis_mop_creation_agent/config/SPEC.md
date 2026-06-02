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
agent.public_repositories_only = true
agent.default_generation_mode = platform-only
local_storage.enabled = true
llm.default_model = gemma4:26b
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
memory.langmem.enabled = true
memory.letta.enabled = false
```

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
