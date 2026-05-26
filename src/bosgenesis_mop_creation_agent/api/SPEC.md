# API Specification

## Intent

`api/` defines the external surfaces for triggering, refining, observing, and retrieving MoP creation runs.

## REST endpoints

Future REST endpoints:

```text
GET  /health
POST /mop-creation/generate
GET  /mop-creation/{mop_id}
GET  /mop-creation/latest
GET  /config/effective
```

## MCP tools

Future on-demand MCP tools:

```text
mop_creation_health
mop_creation_generate
mop_creation_refine
mop_creation_get
mop_creation_latest
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

## Response contract

Responses must include:

- `mop_id`;
- `run_id`;
- `correlation_id`;
- source namespace;
- target namespace;
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

## Behavior

- REST and MCP must call the same orchestration contract.
- REST is the standalone trigger path.
- MCP is the Codex iterative refinement path.
- Health/config responses must redact secrets.
- API code must never call Kubernetes, Helm, databases, caches, or streams directly for evidence; it delegates to orchestration.
