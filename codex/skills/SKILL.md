# BOS Genesis MoP Creation Agent

Use this skill when the user asks Codex to generate, retrieve, inspect, or refine BOS Genesis Method of Procedure documents or installation notes through the `bosgenesis-mop-creation-agent`.

## When to Use

Use this skill for requests involving:

- BOS Genesis MoP creation.
- namespace mirror or reconstruction planning.
- Kubernetes/Helm installation documentation.
- human-readable MoP PDF generation.
- LLM/agent-readable installation notes.
- `bosgenesis-mop-creation-agent`.
- `mop_creation_*` MCP tools.

## MCP Server

Use the configured MCP server:

```toml
[mcp_servers.bosgenesis_mop_creation]
url = "http://mop-creation-agent.bosgenesis.local/mcp"
```

Available tools:

- `mop_creation_health`
- `mop_creation_generate`
- `mop_creation_get`
- `mop_creation_latest`
- `mop_creation_effective_config`

## Safety Rules

- This agent generates documentation and contract responses only.
- Do not execute generated Helm, Kubernetes, database, cache, or stream commands.
- Do not include Kubernetes Secret values or secret-like values.
- Do not copy production data.
- Treat Phase 1 responses as stub contract responses until real generation is implemented.
- For live Kubernetes or Helm inspection, use the dedicated BOS Genesis Kubernetes and Helm MCP servers, not this agent.

## Typical Workflow

1. Check agent health with `mop_creation_health`.
2. Inspect redacted effective config with `mop_creation_effective_config` if needed.
3. Generate a Phase 1 stub response with `mop_creation_generate`.
4. Retrieve a generated response with `mop_creation_get`.
5. Retrieve the latest response with `mop_creation_latest`.

## Generate Request Shape

Use `mop_creation_generate` with:

```json
{
  "source_namespace": "bosgenesis",
  "target_namespace": "bosgenesis-copy-dev",
  "source_snapshot_id": "latest",
  "mode": "platform-only",
  "include_helm": true,
  "include_raw_k8s": true,
  "include_validation_steps": true,
  "include_rollback_steps": true,
  "include_application_schema": false,
  "return_content": false,
  "caller": "codex",
  "correlation_id": "optional-correlation-id"
}
```

## Expected Phase 1 Behavior

The current Phase 1 implementation returns:

- `mop_id`
- `run_id`
- `correlation_id`
- stub `trace_ids`
- stub human MoP PDF path
- stub installation notes path
- warnings confirming no Kubernetes, Helm, Qdrant, or datastore calls were made

No real MoP artifacts are generated yet in Phase 1.

## Example User Requests

- "Generate a MoP stub for bosgenesis into bosgenesis-copy-dev."
- "Check whether the MoP Creation Agent is healthy."
- "Get the latest MoP creation response."
- "Show me the effective config for the MoP Creation Agent."

