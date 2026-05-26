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
- Optional persistence/indexing stores.
- LLM and LangChain settings.
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
llm.default_model = gpt-4.1-mini
memory.langmem.enabled = true
memory.letta.enabled = false
```

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

