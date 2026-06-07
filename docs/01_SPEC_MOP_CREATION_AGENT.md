# BOS Genesis MoP Creation Agent - Specification

**Document status:** Initial scaffold  
**Agent name:** `bosgenesis-mop-creation-agent`  
**Python package:** `bosgenesis_mop_creation_agent`  
**Primary mode:** On-demand only  
**Default source namespace:** `bosgenesis` from configuration  
**Runtime source namespace:** Config default unless switched through REST/MCP namespace APIs  
**Target namespace:** Provided at runtime  
**Execution posture:** Read-only discovery, evidence-grounded reasoning, document generation  
**Primary purpose:** Generate sample-format human Method of Procedure (MoP) artifacts and LLM/agent-readable Markdown installation notes that can recreate or mimic BOS Genesis namespace resources into a target namespace using copyable commands.

The agent is not an executor. It creates a safe, line-by-line human MoP artifact using the approved sample MoP format, with commands, expected outputs, validation checkpoints, rollback notes, and execution log sections. The current implementation writes the human MoP content and a production-readable paginated PDF rendered from the same sample-derived template. It also creates LLM/agent-readable Markdown installation notes and a standalone machine execution YAML plan so another agent can autonomously recreate the target environment. It uses the latest inventory captured by the Analytical MoP ETL Agent and enriches it, when needed, through the existing Helm MCP and Kubernetes Inspector MCP.

The agent is non-deterministic by design. When deterministic evidence is incomplete, it may use LLM reasoning to infer next steps, dependency order, public repository references, chart/value reconstruction, and unknowns. Inferred content must be labeled and traceable. Application-mode schema recreation guidance is deferred to backlog and must not be treated as current Phase 12 scope.

## 1. Product Goal

Create an on-demand MoP Creation Agent that reads the latest namespace inventory from Analytical MoP ETL Agent data stores, optionally revalidates live state through existing governed MCP servers, and writes Kubernetes namespace replication artifacts in the approved MoP style.

The generated human MoP content must allow a human operator to recreate source namespace resources into a runtime-provided target namespace by copying commands step by step. The generated Markdown installation notes and standalone machine execution YAML must allow another LLM or agent to recreate the same namespace structure without populating production data. In Codex/MCP mode, Codex may call the agent repeatedly to generate, retrieve, inspect, and validate artifacts.

## 2. Scope

### In scope

- Read latest source namespace snapshot from PostgreSQL and/or ClickHouse.
- Source namespace defaults to `bosgenesis` from configuration.
- Active source namespace can be switched at runtime through small governed APIs.
- Active source namespace is the primary key for agentic memory and session context.
- Target namespace is supplied at runtime.
- One namespace only and namespace-only scope for v1.
- Kubernetes and Helm based reconstruction.
- Public repositories only for v1.
- Use Kubernetes Inspector MCP for resource-level read enrichment and live validation.
- Use Helm Manager MCP for Helm release, chart, value, manifest, and history enrichment.
- Use Data Ingestion Agent/Analytical MoP ETL evidence when available.
- Query Qdrant for existing vectorized MoP/installation-note references for discovered components when enabled.
- Use matching Qdrant references as non-authoritative prior guidance with citations, confidence, and validation against current evidence.
- Optionally ingest completed, redacted MoP artifacts into Qdrant through an explicit admin API. This ingestion path is separate from generation and requires explicit user confirmation.
- Use optional Phase 10 bounded LLM reasoning only when deterministic reconstruction has gaps or ambiguity. LLM output is schema-validated, confidence-gated, advisory only, and labeled `llm_suggestion_requires_human_review`.
- Generate human MoP content in local storage using the approved sample-derived template, plus a paginated PDF artifact for human review.
- Generate LLM/agent-readable Markdown installation notes in local storage.
- Generate a canonical `machine_execution_plan` YAML block in the Markdown notes and a standalone `machine_execution_plan.yaml` artifact.
- Expose governed artifact preview, full-file download, generated-folder zip archive, and housekeeping delete APIs.
- Integrate with Codex as an on-demand MCP server for generation, retrieval, configuration inspection, artifact preview, and artifact cleanup.
- Run as standalone REST-triggered autonomous agent when Codex is not driving the reasoning loop.
- Use LangGraph with LangChain and a configured LLM profile for standalone reasoning.
- Support `platform-only` mode for Kubernetes and Helm recreation steps.
- Keep `application` mode as a defined but deferred/backlog contract for metadata-only schema/topology recreation guidance; Phase 12 implementation is skipped for now.
- Store MoP metadata and content in MongoDB when enabled.
- Store execution/request metadata in PostgreSQL/ClickHouse when enabled.
- Emit structured audit events, phase latency metrics, warning taxonomy, Langfuse reasoning metadata, and OpenTelemetry/SigNoz spans when enabled.
- Use LangMem-shaped in-process memory, Redis durable short-term memory, and PostgreSQL/pgvector durable episodic memory when Phase 11 memory is enabled.
- Use agentic memory classes including short-term, episodic, and knowledge memory.
- Return generated run directory, artifact manifest, human MoP path, PDF path, Markdown installation notes path, machine plan path, and optionally notes content to caller/Codex.
- Include the Letta adapter interface as disabled future scope.

### Out of scope

- Applying the generated MoP.
- Creating the target namespace automatically.
- Performing anomaly detection.
- Triggering alerts.
- Secret value migration.
- Production data migration or population.
- Cluster-scoped resource migration.
- RBAC migration unless explicitly allowed in a later version.
- Multi-namespace reconstruction.
- Cluster-admin scope.
- Private/custom repository discovery.
- Docker image rebuild inference.
- Letta-backed memory activation.
- Automatic Qdrant ingestion during generation.
- Ungated Qdrant writes, deletes, or re-embedding.
- LLM-generated executable manifests or Helm commands as final truth.
- LLM approval of the final MoP.

## 3. Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | Provide an on-demand API endpoint to generate MoP. |
| FR-2 | Provide MCP tools for Codex-driven generation, retrieval, artifact inspection, artifact cleanup, configuration inspection, and health. |
| FR-3 | Accept target namespace at runtime. |
| FR-3a | Provide APIs to get and switch the active source namespace at runtime. |
| FR-3b | Use `namespace:<active_source_namespace>` as the memory primary key and session context key. |
| FR-4 | Read latest ETL snapshot for active source namespace, unless a generation request provides an explicit per-run source namespace override. |
| FR-5 | Support PostgreSQL and ClickHouse as inventory sources. |
| FR-6 | Optionally call Kubernetes Inspector MCP to validate latest live resources. |
| FR-7 | Optionally call Helm Manager MCP to enrich Helm-managed releases. |
| FR-8 | Classify resources into Helm-managed, raw Kubernetes, excluded, and warning-only categories. |
| FR-9 | Sanitize manifests for target namespace recreation. |
| FR-10 | Exclude or mask blocked/sensitive resources such as Secrets. |
| FR-11 | Generate human MoP content using the approved sample-derived MoP template and write a paginated, production-readable PDF artifact. |
| FR-12 | Generate LLM/agent-readable Markdown installation notes with structured metadata, execution phases, dependencies, validations, unknowns, and a canonical `machine_execution_plan` YAML block. |
| FR-13 | Include document header, summary, pre-checks, backup/reference snapshot, execution, validation, rollback, go/no-go, post-change, and execution log sections. |
| FR-14 | Write human MoP, PDF, Markdown installation notes, machine plan YAML, generated manifests, values files, evidence, and artifact manifest to local file storage. |
| FR-15 | Store MoP and installation notes documents in MongoDB when enabled. |
| FR-16 | Read Qdrant for existing vectorized MoP/installation-note references for relevant components when enabled, and skip gracefully when no matches exist. |
| FR-17 | Emit Langfuse reasoning metadata traces when enabled, without raw prompt or response text. |
| FR-18 | Emit OpenTelemetry/SigNoz phase spans when enabled and SDK/runtime wiring is available; record sink status when unavailable. |
| FR-19 | Return generated file metadata and optional content to caller. |
| FR-20 | Backlog: support `application` mode metadata-only schema/topology output for PostgreSQL, ClickHouse, MongoDB, Redis, and Kafka where approved evidence exists. Phase 12 is skipped for now. |
| FR-21 | Validate generated artifacts for secret leakage, namespace rewrite, blocked resources, production data leakage, and required sections before publication. |
| FR-22 | Support standalone REST-triggered reasoning using LangGraph/LangChain, a configured LLM profile, and optional Phase 11 memory. |
| FR-22a | Support optional Phase 11 memory reads/writes using `namespace:<source_namespace>` with non-secret short-term, episodic, and knowledge summaries. |
| FR-23 | Provide governed REST APIs for artifact preview, full artifact download, generated-folder zip archive, single-run deletion, and bulk artifact cleanup. |
| FR-24 | Provide an optional, config-gated admin API to ingest completed redacted MoP artifacts into Qdrant for future reference lookup. |
| FR-25 | Provide optional bounded LLM reasoning for ambiguity detection, public Helm chart hints, install-order sanity, missing manifest/spec explanations, required human inputs, and confidence labels. |
| FR-26 | Provide Phase 13.1 validation gates that run Ruff, unit tests, JUnit test reports, branch coverage collection, coverage XML, and HTML coverage reports locally and in CI. |

## 4. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Must not require raw kubeconfig. |
| NFR-2 | Must use existing governed MCP servers for live Kubernetes/Helm enrichment. |
| NFR-3 | Must fail gracefully when optional systems are disabled. |
| NFR-4 | Must always keep local storage enabled. |
| NFR-5 | Must not reveal Kubernetes Secret data or secret-like values. |
| NFR-6 | Must be deterministic enough for review and repeat generation once evidence is fixed. |
| NFR-7 | Must generate copyable, exact commands. |
| NFR-8 | Must be traceable from API request to MoP generation output. |
| NFR-9 | Must support configuration-driven enable/disable for PostgreSQL, ClickHouse, MongoDB, read-only Qdrant retrieval, Langfuse, SigNoz, Redis, pgvector, LangMem, and Letta-disabled adapter. |
| NFR-10 | Must label inferred or unknown installation details instead of presenting them as observed facts. |
| NFR-11 | Must never copy production data in platform-only or application mode. |
| NFR-12 | Must record every phase, MCP call summary, Qdrant lookup, reasoning decision, generated-step evidence check, validation result, rendering decision, memory read/write, and response result with `run_id`, `correlation_id`, and trace context. |
| NFR-13 | Must keep generation-time Qdrant access read-only; Qdrant ingestion must be explicit, gated, and outside the generation flow. |
| NFR-14 | Validation reports must be reproducible through `playbook/test-report.sh` and `playbook/test-report.ps1`, ignored by git, and free of credentials, raw prompts, and production data. |

## 5. Runtime Modes

Only one scheduling mode is required for v1:

```text
on_demand
```

The agent runs when called by Codex, another agent, BOS AI Studio, curl, or n8n. It does not run periodically.

Two invocation styles are required:

- Codex-integrated MCP mode, where Codex drives generation, retrieval, inspection, and iterative reasoning outside the agent when needed.
- Standalone REST-triggered mode, where LangGraph coordinates the autonomous reasoning loop and LangChain/model adapters call the configured external LLM.

## 6. Generation Modes

```text
platform-only
application
```

- `platform-only`: generate Kubernetes and Helm recreation steps only.
- `application`: backlog/deferred mode. It remains part of the long-term contract, but Phase 12 implementation is skipped for now; current generation should be treated as `platform-only` unless a future phase reactivates application mode.

When application mode is later implemented, it must not export rows, documents, messages, cache values, files, or other production data.

## 7. API Contract

### POST `/mop-creation/generate`

Generation is asynchronous. `POST /mop-creation/generate` starts a run and
returns HTTP 202 with `status=accepted`. The caller must poll
`GET /mop-creation/{mop_id}` until the status becomes `generated` or `failed`.

Request:

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
  "correlation_id": "optional-uuid"
}
```

Response:

```json
{
  "status": "accepted",
  "mop_id": "mop-uuid",
  "run_id": "run-uuid",
  "correlation_id": "correlation-uuid",
  "source_namespace": "bosgenesis",
  "target_namespace": "bosgenesis-copy-dev",
  "session_context_key": "namespace:bosgenesis",
  "local_file_path": "",
  "mongo_saved": false,
  "qdrant_reference_count": 0,
  "qdrant_lookup_status": "not_executed",
  "memory_status": "pending",
  "memory_read_count": 0,
  "memory_written_count": 0,
  "resource_count": 0,
  "helm_release_count": 0,
  "helm_managed_resource_count": 0,
  "raw_k8s_resource_count": 0,
  "excluded_resource_count": 0,
  "warning_only_resource_count": 0,
  "warning_count": 0
}
```

Polling response after completion:

```json
{
  "status": "generated",
  "mop_id": "mop-uuid",
  "run_id": "run-uuid",
  "correlation_id": "correlation-uuid",
  "source_namespace": "bosgenesis",
  "target_namespace": "bosgenesis-copy-dev",
  "session_context_key": "namespace:bosgenesis",
  "local_file_path": "/data/mops/<mop-id>/mop-bosgenesis-to-bosgenesis-copy-dev-20260522.pdf",
  "mongo_saved": true,
  "qdrant_reference_count": 3,
  "qdrant_lookup_status": "references_found",
  "memory_status": "ok",
  "memory_read_count": 5,
  "memory_written_count": 3,
  "resource_count": 42,
  "helm_release_count": 5,
  "helm_managed_resource_count": 25,
  "raw_k8s_resource_count": 14,
  "excluded_resource_count": 3,
  "warning_only_resource_count": 2,
  "classification_summary": {
    "enabled": true,
    "helm_managed_resource_count": 25,
    "raw_k8s_resource_count": 14,
    "excluded_resource_count": 3,
    "warning_only_resource_count": 2,
    "warnings": [
      "manual_review_required:Pod:8_runtime_artifacts_skipped"
    ]
  },
  "warning_count": 1,
  "trace_ids": {
    "langfuse": "langfuse-trace-id",
    "signoz": "otel-trace-id"
  },
  "artifacts": {
    "run_directory_path": "/data/mops/<mop-id>",
    "artifact_manifest_path": "/data/mops/<mop-id>/artifact.json",
    "human_mop_markdown_path": "/data/mops/<mop-id>/human-mop/mop-bosgenesis-to-bosgenesis-copy-dev-20260522.md",
    "human_mop_pdf_path": "/data/mops/<mop-id>/human-mop/mop-bosgenesis-to-bosgenesis-copy-dev-20260522.pdf",
    "installation_notes_path": "/data/mops/<mop-id>/installation-notes/mop-bosgenesis-to-bosgenesis-copy-dev-20260522.installation.md",
    "machine_execution_plan_path": "/data/mops/<mop-id>/installation-notes/machine_execution_plan.yaml"
  }
}
```

## 8. MCP Tool Contract

Namespace context APIs:

```text
GET /namespace
PUT /namespace
```

`GET /namespace` returns configured namespace, active runtime namespace,
`session_context_key`, and `memory_primary_key`. `PUT /namespace` switches the
active runtime source namespace for future generation requests that do not
explicitly set `source_namespace`. Namespace values must be valid Kubernetes
RFC1123 labels.

Initial MCP tools:

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

The MCP surface is intended for Codex and other agents to request generation, retrieve run metadata, inspect artifact previews, delete generated artifacts, and review configuration without bypassing the governed evidence boundaries.

The REST surface also exposes:

```text
GET /mop-creation/{mop_id}/classification
GET /mop-creation/{mop_id}/artifacts
GET /mop-creation/{mop_id}/artifacts/preview?path=<relative-artifact-path>
GET /mop-creation/{mop_id}/artifacts/download?path=<relative-artifact-path>
GET /mop-creation/{mop_id}/artifacts/archive?prefix=<relative-artifact-directory>
DELETE /mop-creation/{mop_id}
DELETE /mop-creation?confirm=true
```

The classification endpoint returns a safety/classification audit summary with counts, reasons, evidence references, and resource-level categories. Artifact endpoints are intended for deploy smoke tests, Codex validation, direct file retrieval, generated-folder zip downloads, and bounded cleanup without shell access to the pod/PVC.

## 9. Configuration

Credential operations are defined in `docs/CREDENTIALS.md`. Tracked Helm values
must contain only non-secret defaults such as service endpoints, enablement
flags, ports, collection names, and table names. Real credentials and sensitive
DSNs must be supplied through the ignored
`charts/bosgenesis-mop-creation-agent/values.credentials.yaml` file, an external
secure values file passed with `HELM_VALUES_FILE`, or an equivalent secret
manager integration. `/config/effective`, generated artifacts, logs, Langfuse
metadata, and SigNoz span attributes must redact credential-like values.

```yaml
agent:
  name: bosgenesis-mop-creation-agent
  mode: on_demand
  source_namespace: bosgenesis
  local_storage_enabled: true
  local_storage_path: /data/mops
  default_generation_mode: platform-only
  public_repositories_only: true

release:
  values_schema_version: phase15.rc.v1
  release_candidate: phase15-rc1
  app_version: "0.1.0"
  docs_version: phase15

mcp:
  k8s_inspector:
    enabled: true
    endpoint: http://k8s-inspector.bosgenesis.local/mcp
  helm_manager:
    enabled: true
    endpoint: http://helm-manager.bosgenesis.local/mcp
  data_ingestion_agent:
    enabled: true
    endpoint: http://data-ingestion-agent.bosgenesis.local/mcp

storage:
  postgres:
    enabled: true
  clickhouse:
    enabled: true
  mongodb:
    enabled: true
  redis:
    enabled: false
  pgvector:
    enabled: false

retrieval:
  qdrant:
    enabled: true
    mode: read_only
    collection: mop_installation_notes
    top_k: 5
    min_score: 0.72
    ingestion_owned_by: separate-agent
    ingestion_api_enabled: true
    ingestion_vector_size: 384

observability:
  langfuse_enabled: true
  langfuse_endpoint: http://langfuse-web.bosgenesis.svc.cluster.local:3000
  langfuse_public_key: secret-provided
  langfuse_secret_key: secret-provided
  signoz_enabled: true
  otlp_endpoint: http://signoz-otel-collector.signoz.svc.cluster.local:4317
  audit_enabled: true
  phase_metrics_enabled: true
  warning_taxonomy_enabled: true

memory:
  enabled: false
  langmem_enabled: true
  short_term_enabled: true
  episodic_enabled: true
  knowledge_enabled: true
  max_context_items: 5
  max_summary_chars: 800
  redis:
    enabled: true
    db: 0
    key_prefix: mop-agent-memory
  pgvector:
    enabled: true
    dsn: ""  # injected through MEMORY_PGVECTOR_DSN secret/env in deployments
    table: mop_agent_memory
  qdrant:
    enabled: false
    collection: mop_agent_memory
  letta:
    enabled: false
    code_available: true

llm:
  standalone_enabled: true
  framework: langgraph-langchain
  default_model: gemma4:26b
```

## 10. Human MoP and Installation Notes Output Structure

The human MoP content must use the approved sample-derived format:

1. Title
2. Document Header
3. Change Summary
4. Pre-change Checklist
5. Access & Environment Verification
6. Pre-change Backup
7. Stakeholder Notification
8. Deployment Execution
9. Validation
10. Go / No-Go Decision Points
11. Rollback Procedure
12. Post-Change Activities
13. Execution Log
14. Footer

The current PDF artifact is rendered by the Phase 7 professional PDF renderer using `professional_mop_pdf_template.yaml` and the resolved generation context. The renderer provides a colored cover page, executive summary, namespace analytical summary, document quality analysis, scope/evidence controls, platform inventory overview, operator execution plan, full ordered execution commands from `machine_execution_plan`, go/no-go and rollback controls, a human-readable validation/evidence matrix with copy-pasteable validation commands, and grouped Appendix A resource tables. It preserves shell syntax inside command blocks, wraps text and command blocks, adds page footers, prevents table/code overlap, and records template id/version, page count, section order, and overflow count in `artifact.json`.

The Markdown installation notes must include structured metadata, execution phases, dependency graph, command blocks, expected outcomes, validation checks, rollback hints, evidence references, confidence markers, inference labels, and required human inputs. The Markdown must start from a canonical `machine_execution_plan` YAML block, and the same plan must be available as a standalone YAML artifact with YAML aliases disabled.

## 11. Safety Rules

- Never include Secret data.
- Never include secret-like values from environment variables, values files, manifests, schemas, connection strings, or traces.
- Warn that ServiceAccount, Role, RoleBinding, cluster-scoped objects, PVs, CRDs, and node resources are excluded unless future policy allows them.
- Every command must include source or target namespace explicitly.
- All apply commands should recommend `--dry-run=server -o yaml` before real apply.
- Helm commands should include `--dry-run` before real install/upgrade.
- Generated manifests must remove runtime metadata: `uid`, `resourceVersion`, `managedFields`, `creationTimestamp`, `generation`, `ownerReferences`, and `status`.
- Generated manifests must rewrite namespace to target namespace.
- Backlog application mode, when implemented later, must recreate schemas/topology only, not data.
- Qdrant references must be treated as prior guidance only, never as current observed namespace facts.
- The agent must not execute generated commands.

## 12. Acceptance Criteria

| ID | Criteria |
|---|---|
| AC-1 | API can generate MoP for source `bosgenesis` and target namespace from request. |
| AC-2 | MCP tool can trigger MoP generation for Codex. |
| AC-3 | Human MoP content and a paginated PDF are written to local storage. |
| AC-4 | If MongoDB is enabled, MoP is stored in MongoDB. |
| AC-5 | If Qdrant retrieval is enabled, matching prior MoP/installation-note references are cited when available and skipped with a warning when unavailable. |
| AC-6 | If Langfuse is enabled, reasoning metadata trace status is recorded without raw prompt/response text. |
| AC-7 | If SigNoz is enabled and OTel SDK/runtime wiring exists, phase spans are emitted; artifact metadata records sink status either way. |
| AC-8 | MoP includes Helm and raw Kubernetes sections when data exists. |
| AC-9 | MoP excludes or masks sensitive resources. |
| AC-10 | MoP contains copyable commands and expected outputs. |
| AC-10a | Professional PDF command blocks preserve shell operators such as `&&`, `||`, and pipes exactly. |
| AC-10b | Professional PDF validation content is human-readable and copy-pasteable, not raw YAML or JSON. |
| AC-11 | Agent does not execute generated commands. |
| AC-12 | Generated manifests use the target namespace and omit runtime metadata. |
| AC-13 | Backlog: future application mode includes only metadata/schema/topology and no production data. Current active scope is platform-only. |
| AC-14 | Artifact validation fails publication if secret-like values are detected. |
| AC-15 | Markdown installation notes and standalone machine execution YAML are generated alongside the human MoP artifacts. |
| AC-16 | Standalone REST mode can use LangGraph/LangChain, configured LLM, and optional Phase 11 memory without Codex. |
| AC-17 | Artifact preview, full-file download, and generated-folder zip archive endpoints can retrieve generated outputs without shell access. |
| AC-18 | Single-run and bulk housekeeping delete APIs remove only files under the configured artifact storage root. |
| AC-19 | When memory is enabled, generation reads namespace-scoped prior context, writes non-secret summaries, reports memory status/read/write counts, persists short-term records in Redis, persists episodic records in PostgreSQL/pgvector, and continues with warnings if an optional memory backend is unavailable. |
