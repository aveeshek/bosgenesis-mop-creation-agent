# BOS Genesis MoP Creation Agent

Use this skill when Codex needs to generate, retrieve, inspect, download, archive,
clean up, or review BOS Genesis Method of Procedure documents and installation
notes through `bosgenesis-mop-creation-agent`.

## When To Use

Use this skill for:

- Namespace mirror or reconstruction planning.
- Human-readable MoP PDF generation.
- Machine/LLM-readable installation notes Markdown.
- Machine execution plan YAML review.
- Generated Kubernetes resource bundle download.
- Runtime source namespace inspection or switching.
- Kubernetes/Helm platform-only installation documentation.
- Deferred application-mode smoke checks and human-review placeholders.
- Classification, safety, warning, Qdrant, memory, and observability review.
- `bosgenesis-mop-creation-agent` or `mop_creation_*` MCP tool requests.

## MCP Server

Configured MCP server:

```toml
[mcp_servers.bosgenesis_mop_creation]
url = "http://mop-creation-agent.bosgenesis.local/mcp"
```

Available MCP tools:

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

Use MCP for normal Codex-driven generation and inspection. Use REST download
endpoints when binary files or full artifact archives are needed.

## REST Base URL

```text
http://mop-creation-agent.bosgenesis.local
```

Useful REST endpoints:

```text
GET    /health
GET    /config/effective
GET    /namespace
PUT    /namespace
POST   /mop-creation/generate
GET    /mop-creation/{mop_id}
GET    /mop-creation/latest
GET    /mop-creation/{mop_id}/classification
GET    /mop-creation/{mop_id}/artifacts
GET    /mop-creation/{mop_id}/artifacts/preview?path=<relative-path>
GET    /mop-creation/{mop_id}/artifacts/download?path=<relative-path>
GET    /mop-creation/{mop_id}/artifacts/archive?prefix=generated/
DELETE /mop-creation/{mop_id}
DELETE /mop-creation?confirm=true
POST   /references/qdrant/ingest-mop
```

Qdrant ingestion is explicit/admin-only. Generation must not write to Qdrant.

## Safety Rules

- This agent generates documentation and artifact bundles only.
- Do not execute generated Helm, Kubernetes, database, cache, or stream commands
  unless the user explicitly asks for a separate execution workflow.
- Do not include Kubernetes Secret values, credentials, tokens, passwords, or
  secret-like values.
- Do not copy production data.
- Treat Qdrant references and memory context as prior guidance only, never as
  current observed facts.
- Treat LLM output as advisory only. Accepted LLM findings must be labeled
  `llm_suggestion_requires_human_review`.
- The authority order is:

```text
Observed evidence > deterministic reconstruction > Qdrant prior references > LLM suggestion > human approval
```

- For live Kubernetes or Helm mutation, use the dedicated BOS Genesis Kubernetes
  and Helm MCP servers with their safety policies.

## Namespace Workflow

The active source namespace is part of the session and memory key.

Check namespace:

```json
{}
```

with `mop_creation_get_namespace`.

Switch namespace:

```json
{
  "namespace": "signoz",
  "caller": "codex"
}
```

with `mop_creation_set_namespace`.

When the Kubernetes Inspector MCP supports `k8s_set_namespace`, the MoP agent
synchronizes that upstream inspector namespace before live enrichment. The
inspector must also have Kubernetes RBAC in the selected namespace.

## Generation Workflow

1. Call `mop_creation_health`.
2. Call `mop_creation_get_namespace`; switch it if the user requested another
   source namespace.
3. Optionally call `mop_creation_effective_config` to verify redacted config,
   memory, Qdrant, LLM, and observability settings.
4. Call `mop_creation_generate`.
5. Poll `mop_creation_get` until status is not `accepted` or `running`.
6. Review response counts, warnings, trace IDs, memory status, and Qdrant status.
7. Call `mop_creation_classification` and `mop_creation_artifacts` if deeper
   review is needed.
8. Use REST artifact download/archive endpoints for PDF, Markdown, YAML, and zip
   files.

## Generate Request Shape

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

Use `mode="application"` only as a safe smoke/deferred mode unless a future phase
reactivates real application metadata generation. It must not emit executable
schema/data mutation commands without validated evidence and human review.

## Expected Response

Generation is asynchronous. The first response is usually `status=accepted`.
Poll `mop_creation_get` with the returned `mop_id`.

Completed responses include:

- `mop_id`, `run_id`, and `correlation_id`.
- `source_namespace`, `target_namespace`, and `session_context_key`.
- artifact paths for human MoP PDF, human MoP Markdown, installation notes
  Markdown, machine execution YAML, generated manifests, and `artifact.json`.
- inventory source and resource counts.
- Helm-managed, raw Kubernetes, excluded, and warning-only counts.
- `qdrant_lookup_status` and `qdrant_reference_count`.
- `memory_status`, `memory_read_count`, and `memory_written_count`.
- warning list and trace IDs for Langfuse/SigNoz.

## Download Artifacts

Get artifact index:

```powershell
$mopId = "<mop-id>"
Invoke-RestMethod "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts" |
  ConvertTo-Json -Depth 20
```

Download artifact by relative path from the index:

```powershell
Invoke-WebRequest `
  "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts/download?path=<relative-path>" `
  -OutFile ".\<local-file>"
```

Download generated Kubernetes resources as zip:

```powershell
Invoke-WebRequest `
  "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts/archive?prefix=generated/" `
  -OutFile ".\generated-kubernetes-resources.zip"
```

Common files:

- `*.pdf`: human-readable MoP.
- `*.installation.md`: machine-readable installation notes.
- `machine_execution_plan.yaml`: structured execution plan.
- `artifact.json`: full artifact manifest, warnings, evidence, and diagnostics.
- `generated/*.yaml`: normalized raw Kubernetes manifests.
- `values/*.yaml`: redacted Helm values when Helm evidence exists.

## Artifact QA Checklist

Before telling the user the MoP is good:

- `status` is `generated`.
- source namespace is the requested namespace.
- generated manifests contain the target namespace, not the source namespace.
- no `secret-*.yaml` manifests or Secret values are present.
- policy-denial warnings are absent or clearly explained.
- Pods are warning-only/runtime artifacts and skipped.
- Qdrant references are cited only as prior guidance.
- LLM reasoning is either `deterministic_sufficient`, `generated`, or safely
  quarantined with warnings.
- Langfuse/SigNoz trace IDs are present when observability is enabled.

## Memory Behavior

Memory is namespace-scoped by `session_context_key`, for example
`namespace:bosgenesis` or `namespace:signoz`.

Expected durable backends:

- Short-term run memory: Redis.
- Episodic generation memory: PostgreSQL/pgvector.
- LangMem-shaped in-process memory: first/cache layer.
- Qdrant and Letta memory adapters: disabled future scope.

Memory must store only non-secret summaries.

## Example User Requests

- "Generate a MoP for bosgenesis into bosgenesis-copy-dev."
- "Switch the source namespace to signoz and generate a platform-only MoP."
- "Download the human-readable MoP PDF and machine-readable installation notes."
- "Download the generated Kubernetes resources zip."
- "Show the classification summary and warnings for the latest MoP."
- "Delete this MoP run and its artifacts."
- "Show the effective config with credentials redacted."
