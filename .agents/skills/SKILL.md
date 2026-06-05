# BOS Genesis MoP Creation Agent

Use this skill when Codex needs to generate, retrieve, inspect, download, archive, clean up, or review BOS Genesis Method of Procedure documents and installation notes through the `bosgenesis-mop-creation-agent` MCP server.

## When to Use

Use this skill for requests involving:

- BOS Genesis MoP creation.
- Namespace mirror or reconstruction planning.
- Kubernetes/Helm installation documentation.
- Human-readable MoP PDF generation.
- LLM/agent-readable installation notes.
- Machine execution plan YAML retrieval.
- Runtime source namespace inspection or switching.
- Artifact preview, download, archive, or housekeeping cleanup.
- Qdrant prior-reference lookup or explicit gated MoP artifact ingestion.
- Phase 11 memory status validation.
- `bosgenesis-mop-creation-agent`.
- `mop_creation_*` MCP tools.

## MCP Server

Use the configured MCP server:

```toml
[mcp_servers.bosgenesis_mop_creation]
url = "http://mop-creation-agent.bosgenesis.local/mcp"
```

Common tools:

- `mop_creation_health`
- `mop_creation_get_namespace`
- `mop_creation_set_namespace`
- `mop_creation_generate`
- `mop_creation_get`
- `mop_creation_latest`
- `mop_creation_classification`
- `mop_creation_artifacts`
- `mop_creation_artifact_preview`
- `mop_creation_delete`
- `mop_creation_delete_all`
- `mop_creation_effective_config`

## Safety Rules

- This agent generates documentation and artifact bundles only.
- Do not execute generated Helm, Kubernetes, database, cache, or stream commands unless the user explicitly asks in a separate execution workflow.
- Do not include Kubernetes Secret values or secret-like values.
- Do not copy production data.
- Treat Qdrant references and memory context as prior guidance only, never as current observed facts.
- LLM findings are advisory only and must be labeled `llm_suggestion_requires_human_review` when present.
- For live Kubernetes or Helm mutation, use the dedicated BOS Genesis Kubernetes and Helm MCP servers with their safety policy.

## Typical Workflow

1. Check agent health with `mop_creation_health`.
2. Optionally inspect or switch the active source namespace.
3. Inspect redacted effective config when validating memory, LLM, Qdrant, or artifact settings.
4. Start generation with `mop_creation_generate`.
5. Poll with `mop_creation_get` until status is `generated` or `failed`.
6. Review classification and artifact metadata.
7. Preview or download the PDF, Markdown installation notes, machine execution YAML, or generated-folder archive.

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

## Expected Behavior

The current implementation starts generation asynchronously and returns `status=accepted`. Poll `mop_creation_get` until the run completes.

Completed responses include:

- `mop_id`, `run_id`, and `correlation_id`.
- Source and target namespace.
- `session_context_key` such as `namespace:bosgenesis`.
- Artifact paths for human MoP PDF, human MoP Markdown, installation notes Markdown, machine execution YAML, and `artifact.json`.
- Inventory, Helm, raw Kubernetes, excluded, and warning-only counts.
- Qdrant reference status/count when prior-reference lookup is enabled.
- Memory status/read/write counts when Phase 11 memory is enabled.
- Warnings and trace identifiers.

Phase 11 memory stores only non-secret summaries. Redis persists short-term records, PostgreSQL/pgvector persists episodic records, LangMem-shaped in-process memory acts as first/cache, and Qdrant/Letta memory adapters remain disabled future scope.

## Example User Requests

- "Generate a MoP for bosgenesis into bosgenesis-copy-dev."
- "Check whether the MoP Creation Agent is healthy."
- "Get the latest MoP creation response."
- "Show me the effective config for the MoP Creation Agent."
- "Download the machine execution plan YAML."
- "Show memory status for the latest generated MoP."