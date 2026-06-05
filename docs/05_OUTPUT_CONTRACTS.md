# Output Contracts Specification

**Document status:** Initial scaffold  
**Applies to:** Human MoP content, paginated PDF output, LLM/agent-readable Markdown installation notes, standalone machine execution YAML, generated manifest/value snippets, metadata responses, artifact lifecycle APIs, and optional retrieval references.

## 1. Purpose

This document defines the expected output contracts for `bosgenesis-mop-creation-agent`.

Outputs must align with the SPEC, HLD, LLD, and algorithm design:

- the agent generates procedures and artifacts only;
- the agent does not execute generated commands;
- source namespace defaults to `bosgenesis`;
- target namespace is supplied at runtime;
- generated artifacts must be safe, traceable, reproducible, and free of secret values or production data;
- inferred content must be labeled with confidence and rationale.

## 2. Primary Human MoP Contract

The human-readable PDF MoP is the required primary review artifact. It must follow the approved professional section order:

1. Title and Cover Page
2. Executive Summary
3. Namespace Analytical Summary
4. Document Quality Analysis
5. Scope, Source Evidence, and Controls
6. Recreated Platform Inventory
7. Execution Plan - Operator View
8. Actual Execution Steps - Command Pattern
9. Go / No-Go and Rollback Controls
10. Validation and Evidence Matrix
11. Appendix A - Resource List Snapshot

The current PDF artifact is rendered from the professional PDF YAML template and generation context. It must preserve this section order, use the configured color theme, keep the full ordered execution commands readable, include controls/evidence views, render validation as human-readable copy-pasteable steps, render Appendix A as grouped resource tables, preserve shell command syntax exactly, and record renderer metadata in `artifact.json`.

The professional PDF must not include the removed `Kubernetes Topology View` or `Platform Dependency Map` sections.

## 3. Human MoP Section Requirements

| Section | Required content |
|---|---|
| Document Header | `mop_id`, `run_id`, `correlation_id`, source namespace, target namespace, generation mode, generated timestamp, caller, snapshot ID/timestamp when known. |
| Change Summary | What will be recreated, counts of Helm releases, raw Kubernetes resources, excluded resources, warnings, and application-mode targets if selected. |
| Pre-change Checklist | Operator prerequisites, access checks, tool availability, context checks, and required approvals. |
| Access and Environment Verification | Copyable commands to confirm Kubernetes/Helm context and target namespace readiness. |
| Pre-change Backup | Export/reference source manifests, Helm values, and evidence snapshots without exposing secrets. |
| Stakeholder Notification | Placeholder notification text for start, rollback, and completion messages. |
| Deployment Execution | Target namespace preparation, secret placeholders, Helm releases, raw Kubernetes resources, and ingress. Future/backlog application schema steps may be added when application mode is reactivated. |
| Validation Steps | Pod, deployment, service, ingress, Helm, and PVC validation checks. Future/backlog application-mode validation checks may be added when application mode is reactivated. |
| Validation and Evidence Matrix | Human-readable evidence source rows plus ordered copy-pasteable validation commands from the `validate` phase of `machine_execution_plan`; raw YAML/JSON dumps and internal MCP reference lists are not allowed in this human section. |
| Appendix A - Resource List Snapshot | Grouped tables for Helm releases and Kubernetes resource kinds, including deployments, statefulsets, daemonsets, services, ingresses, configmaps, PVCs, jobs, cronjobs, pods, warning-only items, and excluded resources when present. |
| Go/No-Go Decision Points | Explicit stop/continue checkpoints and failed-action guidance. |
| Rollback Procedure | Helm uninstall and raw manifest delete guidance. Future/backlog application-mode cleanup guidance must be cautious and manual-review-first when reactivated. |
| Post-change Activities | Documentation, trace/artifact retention, and handoff notes. |
| Execution Log | Blank operator-fillable execution table. |
| Footer | MoP generation metadata including source namespace, target namespace, run ID, and correlation ID. |

## 4. Markdown Installation Notes Contract

The installation notes are the required second primary artifact. They must be Markdown and optimized for autonomous execution by another LLM/agent.

It must include:

- machine-parseable metadata;
- source namespace, target namespace, generation mode, `run_id`, `correlation_id`, and evidence timestamp;
- a canonical `machine_execution_plan` YAML block that downstream agents parse before prose sections;
- execution phases;
- dependency graph or ordered dependency list;
- command blocks;
- expected outcomes;
- validation checks;
- rollback hints;
- evidence references;
- inference labels, confidence, and rationale;
- unknowns and required human inputs;
- explicit no-data-copy and no-secret constraints.

The `machine_execution_plan` block must contain:

- `schema_version`;
- `authority_order`;
- `executor_contract`;
- `dependency_graph`;
- `required_human_inputs`;
- `phases[]`;
- `steps[]` under each phase.

Each step must include stable `step_id`, `phase_id`, `type`, `depends_on`, `commands`, `expected_outcomes`, `evidence_refs`, `qdrant_refs`, `inference.label`, `inference.confidence`, `inference.rationale`, `required_human_inputs`, `rollback_commands`, `mutates_target`, and `requires_human_approval`.

The notes filename should use:

```text
/data/mops/<mop-id>/installation-notes/<file-name>.installation.md
/data/mops/<mop-id>/installation-notes/machine_execution_plan.yaml
```

## 5. Command Contract

All executable commands in the MoP must be copyable and namespace-explicit. Human PDF command blocks must preserve shell syntax exactly, including `&&`, `||`, pipes, quotes, multiline continuations, and target namespace arguments.

Helm command pattern:

```bash
helm upgrade --install <release-name> <chart-ref> \
  --namespace <target-namespace> \
  --create-namespace \
  -f values-<release-name>.yaml \
  --dry-run

helm upgrade --install <release-name> <chart-ref> \
  --namespace <target-namespace> \
  --create-namespace \
  -f values-<release-name>.yaml \
  --atomic \
  --timeout 10m
```

Raw Kubernetes command pattern:

```bash
kubectl apply -f generated/<kind>-<name>.yaml -n <target-namespace> --dry-run=server -o yaml
kubectl apply -f generated/<kind>-<name>.yaml -n <target-namespace>
```

If a chart reference, value, resource, or ordering decision is inferred rather than observed, the MoP must label it as inferred and require human confirmation.

## 6. Generated File Contract

Local storage is mandatory. A successful run must produce:

```text
/data/mops/<mop-id>/artifact.json
/data/mops/<mop-id>/human-mop/<file-name>.md
/data/mops/<mop-id>/human-mop/<file-name>.pdf
/data/mops/<mop-id>/installation-notes/<file-name>.installation.md
/data/mops/<mop-id>/installation-notes/machine_execution_plan.yaml
```

When generated snippets exist, they must be referenced from the MoP and stored under:

```text
/data/mops/<mop-id>/generated/*.yaml
/data/mops/<mop-id>/values/*.yaml
/data/mops/<mop-id>/evidence/*.json
```

Generated manifests must:

- rewrite `metadata.namespace` to the target namespace;
- remove runtime metadata;
- exclude blocked resource kinds;
- contain no secret values or production data;
- redact secret-like scalar values in generated raw manifests, including
  environment variables whose names contain password, token, secret, credential,
  key, or similar sensitive markers.

Phase 6 platform-only generation must also write redacted Helm values files under:

```text
/data/mops/<mop-id>/values/values-<release>.yaml
```

The values files must preserve non-sensitive overrides and replace secret-like
values with placeholders.

## 7. API Response Contract

Generation is asynchronous:

```text
POST /mop-creation/generate -> HTTP 202, status=accepted
GET  /mop-creation/{mop_id} -> status=accepted | generated | failed
GET  /namespace -> active source namespace and session context key
PUT  /namespace -> switch active source namespace
```

When `status=accepted`, identifiers and trace placeholders are available, but
artifact file paths may be empty or point to planned locations. Callers must poll
until `status=generated` before reading artifacts.

The generation response must include:

```text
status
mop_id
run_id
correlation_id
source_namespace
target_namespace
session_context_key
local_file_path
mongo_saved
qdrant_reference_count
qdrant_lookup_status
memory_status
memory_read_count
memory_written_count
resource_count
helm_release_count
helm_managed_resource_count
raw_k8s_resource_count
excluded_resource_count
warning_only_resource_count
classification_summary
warning_count
trace_ids
warnings
created_at
content, only when return_content is true
artifacts.human_mop_pdf_path
artifacts.human_mop_markdown_path
artifacts.installation_notes_path
artifacts.machine_execution_plan_path
artifacts.artifact_manifest_path
artifacts.run_directory_path
```

Optional stores may fail without failing the run, but local storage failure must fail the request.

The artifact manifest must include an `observability` object with `schema_version`, `trace_ids`, `sinks`, `service_details`, `context`, `phase_metrics`, `phase_latency_ms`, `warning_taxonomy`, `audit_events`, `audit_event_count`, and `redaction_status`. `service_details` records redacted non-secret endpoint metadata such as the Langfuse web endpoint and SigNoz OTLP collector endpoint. `sinks` records whether Langfuse and SigNoz export is enabled, disabled, missing credentials, missing SDK packages, or failed configuration/export. Audit events must cover request receipt, memory read/write, snapshot selection, MCP enrichment, classification, Qdrant lookup, rendering, generated-step evidence/inference validation, LLM reasoning metadata, warning taxonomy, and response generation. Raw prompts, raw model responses, manifests, Qdrant excerpts, credentials, and production data are not allowed in observability payloads.

The classification summary must be available in the generation response and through:

```text
GET /mop-creation/{mop_id}/classification
```

The summary must include classification counts, warning summaries, and resource-level category records when requested through the dedicated endpoint. Pod runtime artifacts should be summarized rather than emitted as one warning per Pod.

## 8. Artifact Preview Contract

The agent may expose controlled artifact preview endpoints for deploy testing and
Codex review:

```text
GET /mop-creation/{mop_id}/artifacts
GET /mop-creation/{mop_id}/artifacts/preview?path=<relative-artifact-path>
GET /mop-creation/{mop_id}/artifacts/download?path=<relative-artifact-path>
GET /mop-creation/{mop_id}/artifacts/archive?prefix=<relative-artifact-directory>
DELETE /mop-creation/{mop_id}
DELETE /mop-creation?confirm=true
```

Preview rules:

- only files under the selected `mop_id` artifact directory are readable;
- path traversal and absolute paths are denied;
- only configured extensions are previewable;
- response size is capped by configuration;
- preview can be disabled by configuration;
- preview must not bypass secret exclusion or redaction controls.

Download rules:

- only files under the selected `mop_id` artifact directory are downloadable;
- path traversal and absolute paths are denied;
- only configured artifact extensions are downloadable;
- response content is not truncated;
- response must set a safe attachment filename;
- download must not bypass secret exclusion or redaction controls.

Archive rules:

- only directories under the selected `mop_id` artifact directory are archivable;
- path traversal and absolute paths are denied;
- only configured artifact extensions are included in the zip;
- the zip response must not include files outside the requested relative directory;
- the intended generated-manifest archive path is `prefix=generated/`.

Housekeeping delete rules:

- single-run delete removes only the selected `mop_id` run directory and related in-memory run metadata;
- bulk delete requires `confirm=true`;
- bulk delete removes only directories under the configured local artifact storage root;
- delete responses must include removed file count, removed directory count, and removed byte count;
- delete operations must never remove files outside the configured artifact storage root.

## 9. Phase 6.2 LLM Suggestion Contract

When enabled, the LLM repair layer may add suggestion records to artifact metadata
and inference sections. It must not modify executable YAML or command text.

Every LLM suggestion must include:

```text
target_type
target_name
issue
suggestion
confidence
rationale
evidence_refs
label=llm_suggestion_requires_human_review
executable_yaml_allowed=false
```

The agent must drop LLM suggestions below the configured confidence threshold.

The LLM response must validate against a strict Pydantic envelope:

```text
suggestions[]
```

where each suggestion uses the fields above and `confidence` is a number from
0.0 through 1.0. Prose-only responses, thinking text, malformed JSON, extra
top-level fields, invalid confidence values, or missing required fields must not
be accepted silently.

Artifact metadata must include parser diagnostics:

```text
candidate_count
response_chars
response_source
parse_status
accepted_count
rejected_low_confidence_count
rejected_invalid_count
minimum_confidence
```

These diagnostics must distinguish valid empty responses from invalid structured
output and from low-confidence suggestions filtered by policy.

Phase 10 bounded reasoning artifact metadata must include:

```text
bounded_llm_reasoning.enabled
bounded_llm_reasoning.attempted
bounded_llm_reasoning.status
bounded_llm_reasoning.authority_order
bounded_llm_reasoning.findings[]
bounded_llm_reasoning.diagnostics
```

Every accepted finding must include:

```text
label=llm_suggestion_requires_human_review
authoritative=false
executable_yaml_allowed=false
confidence
rationale
evidence_refs
qdrant_refs
required_human_inputs
```

Bounded reasoning findings may appear in `artifact.json`, the human MoP
Evidence and Inference Appendix, and the Markdown installation notes
`inferences` block. They must not alter generated manifests, Helm values,
machine execution commands, or final MoP approval status.

## 10. MCP Output Contract

MCP tool responses must be agent-readable and include:

- structured metadata fields matching the API response;
- concise human summary;
- artifact retrieval hints;
- warnings and unknowns;
- trace identifiers;
- no secret values.

## 11. Evidence Contract

Every generated step must be grounded by at least one of:

- PostgreSQL ETL snapshot evidence;
- ClickHouse analytical inventory evidence;
- Kubernetes Inspector MCP evidence;
- Helm Manager MCP evidence;
- Data Ingestion Agent evidence;
- Qdrant prior MoP/installation-note references for matching components, when available;
- future/backlog application-mode metadata evidence when application mode is reactivated;
- explicitly labeled inference with confidence and rationale.

Evidence references must appear in the appendix or inline where useful.

Qdrant references must be labeled as prior references, not current observed facts. If no Qdrant match exists for a component, the agent records the no-match status and continues without that reference.

## 10. Safety Contract

The final MoP and generated snippets must not contain:

- Kubernetes Secret data or `stringData`;
- secret-like values from Helm values, environment variables, manifests, schemas, connection strings, or traces;
- production table rows, documents, messages, cache values, uploaded files, or business data;
- executable commands for blocked resource kinds;
- cluster-scoped mutation steps in v1.

Validation failure for secret leakage, blocked resources, or production data leakage must stop artifact publication.

## 11. Optional Store and Retrieval Contracts

MongoDB, PostgreSQL metadata, ClickHouse metrics, Redis, pgvector, LangMem, read-only generation-time Qdrant retrieval, and gated Qdrant artifact ingestion are optional.

Optional persisted records must include:

- `mop_id`;
- `run_id`;
- `correlation_id`;
- source namespace;
- target namespace;
- generation mode;
- section name or artifact type;
- evidence references;
- trace identifiers where available.

Optional stores must receive redacted content only.

Phase 11 memory records are optional store records. They must contain only
non-secret summaries and must be labeled as prior context, not current facts.
Generated API responses and `artifact.json` must expose memory status/read/write
counts and per-backend status without exposing secret-bearing content.

Redis durable memory stores short-term records only under `<key_prefix>:<namespace_key>:records`. PostgreSQL/pgvector durable
memory stores episodic records only through the configured `MEMORY_PGVECTOR_DSN` and table, default `mop_agent_memory`. LangMem-shaped in-process memory stores enabled safe summary kinds for the running process. Qdrant and Letta memory adapters are disabled future scope.

Qdrant retrieval records consumed by the agent must include:

- component identity;
- source artifact type, such as MoP PDF text or Markdown installation notes;
- source artifact ID or URI;
- match score;
- section or chunk identifier;
- ingestion timestamp when available;
- citation text or reference key.

The MoP Creation Agent must not write, upsert, delete, embed, or ingest Qdrant records during generation. Optional Qdrant ingestion is available only through a separate admin REST endpoint, must require `confirm=true`, and must index only completed redacted MoP artifacts.

Optional ingestion endpoint:

```text
POST /references/qdrant/ingest-mop
```

Request:

```json
{
  "mop_id": "mop-uuid",
  "caller": "admin-or-automation",
  "confirm": true
}
```

The ingestion response must include status, `mop_id`, collection name, and inserted point count when successful.
