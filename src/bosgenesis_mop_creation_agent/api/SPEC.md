# API Specification

## Intent

`api/` defines the external surfaces for triggering, refining, observing, and retrieving MoP creation runs.

## REST endpoints

Implemented REST endpoints:

```text
GET  /health
GET  /namespace
PUT  /namespace
POST /mop-creation/generate
GET  /mop-creation/{mop_id}
DELETE /mop-creation/{mop_id}
GET  /mop-creation/latest
GET  /mop-creation/{mop_id}/classification
GET  /mop-creation/{mop_id}/artifacts
GET  /mop-creation/{mop_id}/artifacts/preview?path=<relative-artifact-path>
GET  /mop-creation/{mop_id}/artifacts/download?path=<relative-artifact-path>
GET  /mop-creation/{mop_id}/artifacts/archive?prefix=<relative-artifact-directory>
DELETE /mop-creation?confirm=true
GET  /config/effective
GET  /mcp/tools
POST /mcp/tools/{tool_name}
POST /mcp
POST /references/qdrant/ingest-mop
```

## MCP tools

Implemented on-demand MCP tools:

```text
mop_creation_health
mop_creation_get_namespace
mop_creation_set_namespace
mop_creation_generate
mop_creation_get
mop_creation_latest
mop_creation_classification
mop_creation_artifacts
mop_creation_artifact_preview
mop_creation_delete
mop_creation_delete_all
mop_creation_effective_config
```

## Request contract

`MoPGenerationRequest` must include:

- `source_namespace`: optional string, default from config.
- `target_namespace`: required string.
- `source_snapshot_id`: optional string, default `latest`.
- `mode`: `platform-only` or `application`.
- `include_helm`: bool.
- `include_raw_k8s`: bool.
- `include_validation_steps`: bool.
- `include_rollback_steps`: bool.
- `include_application_schema`: bool.
- `output_artifacts`: list, default `["human_mop_pdf", "installation_notes"]`.
- `return_content`: bool.
- `caller`: string.
- `correlation_id`: optional string.

`QdrantIngestMoPRequest` must include:

- `mop_id`: generated MoP run to index.
- `caller`: caller identity.
- `confirm`: must be `true`.

`NamespaceSwitchRequest` must include:

- `namespace`: active source namespace to use for future generation requests
  that do not explicitly provide `source_namespace`;
- `caller`: caller identity for audit and session context metadata.

Namespace values must be Kubernetes RFC1123 labels.

## Response contract

`POST /mop-creation/generate` must start a background run and return HTTP 202
with `status=accepted`. Callers must poll `GET /mop-creation/{mop_id}` until
the status becomes `generated` or `failed`.

Responses must include:

- `mop_id`;
- `run_id`;
- `correlation_id`;
- source namespace;
- target namespace;
- `session_context_key` as `namespace:<source_namespace>`;
- memory status, memory read count, and memory written count;
- status;
- human MoP PDF file path;
- Markdown installation notes file path;
- optional Markdown installation notes content when requested;
- resource counts;
- Helm release count;
- excluded resource count;
- warning count;
- trace identifiers;
- warnings;
- created timestamp.

Generated artifacts must be available through:

```text
GET /mop-creation/{mop_id}/artifacts
GET /mop-creation/{mop_id}/artifacts/preview?path=<relative-artifact-path>
GET /mop-creation/{mop_id}/artifacts/download?path=<relative-artifact-path>
GET /mop-creation/{mop_id}/artifacts/archive?prefix=<relative-artifact-directory>
DELETE /mop-creation/{mop_id}
DELETE /mop-creation?confirm=true
```

`preview` returns capped inline text for quick inspection. `download` returns the
full artifact file for approved download extensions, including generated PDFs,
and must deny path traversal, absolute paths, and unsupported extensions. `archive` returns a zip
for an approved artifact directory such as `generated/`, includes only approved
artifact extensions, and must deny path traversal.

Housekeeping delete APIs remove local PVC-backed artifacts and in-memory run
records only. `DELETE /mop-creation/{mop_id}` removes one run. Bulk deletion
requires `confirm=true` and removes all run directories under configured local
storage.

## Behavior

- REST and MCP must call the same orchestration contract.
- REST is the standalone trigger path.
- Generation is asynchronous; POST starts a run and GET retrieves current run state.
- `GET /namespace` returns configured namespace, active runtime namespace, and
  namespace-derived memory/session context key.
- `PUT /namespace` switches the active runtime source namespace without changing
  static config; explicit `source_namespace` in a generation request remains a
  per-run override.
- MCP is the Codex iterative refinement path.
- Health/config responses must redact secrets.
- API code must never call Kubernetes, Helm, databases, caches, or streams directly for evidence; it delegates to orchestration.
- Artifact preview is capped for quick inspection.
- Artifact download returns complete approved artifacts, including `.pdf` MoP files.
- Artifact archive returns a zip for approved directories such as `generated/`.
- Housekeeping deletes remove only configured local artifact storage and in-memory run metadata.
- Qdrant ingestion is a separate admin operation, requires explicit user confirmation, and must not run as part of generation.
- Memory is optional; when enabled, generation reads/writes only namespace-scoped
  non-secret summaries and surfaces read/write counts in responses.
