# BOS Genesis MoP Creation Agent - Specification

**Document status:** Initial scaffold  
**Agent name:** `bosgenesis-mop-creation-agent`  
**Python package:** `bosgenesis_mop_creation_agent`  
**Primary mode:** On-demand only  
**Default source namespace:** `bosgenesis` from configuration  
**Target namespace:** Provided at runtime  
**Execution posture:** Read-only discovery, evidence-grounded reasoning, document generation  
**Primary purpose:** Generate a human-executable Method of Procedure (MoP) that can recreate or mimic BOS Genesis namespace resources into a target namespace using copyable commands.

The agent is not an executor. It creates a safe, line-by-line MoP with commands, expected outputs, validation checkpoints, rollback notes, and execution log sections. It also creates an LLM/agent-readable Markdown installation guide so another agent can autonomously recreate the target environment. It uses the latest inventory captured by the Analytical MoP ETL Agent and enriches it, when needed, through the existing Helm MCP and Kubernetes Inspector MCP.

The agent is non-deterministic by design. When deterministic evidence is incomplete, it may use LLM reasoning to infer next steps, dependency order, public repository references, chart/value reconstruction, schema recreation guidance, and unknowns. Inferred content must be labeled and traceable.

## 1. Product Goal

Create an on-demand MoP Creation Agent that reads the latest namespace inventory from Analytical MoP ETL Agent data stores, optionally revalidates live state through existing governed MCP servers, and writes a Kubernetes namespace replication MoP in the approved MoP style.

The generated MoP must allow a human operator to recreate source namespace resources into a runtime-provided target namespace by copying commands step by step. The generated agent-readable guide must allow another LLM or agent to recreate the same namespace structure without populating production data. In Codex/MCP mode, Codex may call the agent repeatedly to generate, critique, and refine both artifacts.

## 2. Scope

### In scope

- Read latest source namespace snapshot from PostgreSQL and/or ClickHouse.
- Source namespace defaults to `bosgenesis` from configuration.
- Target namespace is supplied at runtime.
- One namespace only and namespace-only scope for v1.
- Kubernetes and Helm based reconstruction.
- Public repositories only for v1.
- Use Kubernetes Inspector MCP for resource-level read enrichment and live validation.
- Use Helm Manager MCP for Helm release, chart, value, manifest, and history enrichment.
- Use Data Ingestion Agent/Analytical MoP ETL evidence when available.
- Generate MoP as Markdown file in local storage.
- Generate LLM/agent-readable Markdown installation guide in local storage.
- Integrate with Codex as an on-demand MCP server for iterative refinement.
- Run as standalone REST-triggered autonomous agent when Codex is not driving the reasoning loop.
- Use LangChain with GPT-4.1 mini, or configured equivalent model, for standalone reasoning.
- Support `platform-only` mode for Kubernetes and Helm recreation steps.
- Support `application` mode for metadata-only schema/topology recreation guidance.
- Store MoP metadata and content in MongoDB when enabled.
- Store MoP semantic chunks/embeddings in Qdrant when enabled.
- Store execution/request metadata in PostgreSQL/ClickHouse when enabled.
- Emit traces to Langfuse and OpenTelemetry/SigNoz when enabled.
- Use Redis, pgvector, and LangMem as optional memory/cache/retrieval backends.
- Use agentic memory classes including short-term, episodic, and knowledge memory.
- Return generated MoP file path and optionally file content to caller/Codex.
- Include Letta adapter interface in the future codebase but keep disabled.

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

## 3. Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | Provide an on-demand API endpoint to generate MoP. |
| FR-2 | Provide MCP tools for Codex-driven generation, refinement, retrieval, and health. |
| FR-3 | Accept target namespace at runtime. |
| FR-4 | Read latest ETL snapshot for configured source namespace. |
| FR-5 | Support PostgreSQL and ClickHouse as inventory sources. |
| FR-6 | Optionally call Kubernetes Inspector MCP to validate latest live resources. |
| FR-7 | Optionally call Helm Manager MCP to enrich Helm-managed releases. |
| FR-8 | Classify resources into Helm-managed, raw Kubernetes, excluded, and warning-only categories. |
| FR-9 | Sanitize manifests for target namespace recreation. |
| FR-10 | Exclude or mask blocked/sensitive resources such as Secrets. |
| FR-11 | Generate a MoP in Markdown using the approved MoP structure. |
| FR-12 | Generate an LLM/agent-readable Markdown installation guide with structured metadata, execution phases, dependencies, validations, and unknowns. |
| FR-13 | Include document header, summary, pre-checks, backup/reference snapshot, execution, validation, rollback, go/no-go, post-change, and execution log sections. |
| FR-14 | Write MoP and agent-readable guide to local file storage. |
| FR-15 | Store MoP and guide documents in MongoDB when enabled. |
| FR-16 | Store MoP/guide chunks and metadata in Qdrant when enabled. |
| FR-17 | Emit Langfuse trace when enabled. |
| FR-18 | Emit OpenTelemetry traces to SigNoz when enabled. |
| FR-19 | Return generated file metadata and optional content to caller. |
| FR-20 | Support `application` mode metadata-only schema/topology output for PostgreSQL, ClickHouse, MongoDB, Redis, and Kafka where approved evidence exists. |
| FR-21 | Validate generated artifacts for secret leakage, namespace rewrite, blocked resources, production data leakage, and required sections before publication. |
| FR-22 | Support standalone REST-triggered reasoning using LangChain, GPT-4.1 mini or configured equivalent, and LangMem-backed memory. |

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
| NFR-9 | Must support configuration-driven enable/disable for PostgreSQL, ClickHouse, MongoDB, Qdrant, Langfuse, SigNoz, Redis, pgvector, LangMem, and Letta-disabled adapter. |
| NFR-10 | Must label inferred or unknown installation details instead of presenting them as observed facts. |
| NFR-11 | Must never copy production data in platform-only or application mode. |
| NFR-12 | Must record every tool call, reasoning decision, generated step, and validation result with `run_id`, `correlation_id`, and trace context. |

## 5. Runtime Modes

Only one scheduling mode is required for v1:

```text
on_demand
```

The agent runs when called by Codex, another agent, BOS AI Studio, curl, or n8n. It does not run periodically.

Two invocation styles are required:

- Codex-integrated MCP mode, where Codex drives iterative reasoning and refinement.
- Standalone REST-triggered mode, where LangChain and the configured external LLM perform the autonomous reasoning loop.

## 6. Generation Modes

```text
platform-only
application
```

- `platform-only`: generate Kubernetes and Helm recreation steps only.
- `application`: include platform-only output plus metadata-only schema/topology recreation guidance for supported databases, caches, and streams.

Application mode must not export rows, documents, messages, cache values, files, or other production data.

## 7. API Contract

### POST `/mop-creation/generate`

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
  "status": "success",
  "mop_id": "mop-uuid",
  "run_id": "run-uuid",
  "correlation_id": "correlation-uuid",
  "source_namespace": "bosgenesis",
  "target_namespace": "bosgenesis-copy-dev",
  "local_file_path": "/data/mops/mop-bosgenesis-to-bosgenesis-copy-dev-20260522.md",
  "mongo_saved": true,
  "qdrant_saved": true,
  "resource_count": 42,
  "helm_release_count": 5,
  "excluded_resource_count": 3,
  "warning_count": 1,
  "trace_ids": {
    "langfuse": "langfuse-trace-id",
    "signoz": "otel-trace-id"
  },
  "artifacts": {
    "human_mop_path": "/data/mops/mop-bosgenesis-to-bosgenesis-copy-dev-20260522.md",
    "agent_guide_path": "/data/mops/mop-bosgenesis-to-bosgenesis-copy-dev-20260522.agent.md"
  }
}
```

## 8. MCP Tool Contract

Initial MCP tools:

```text
mop_creation_health
mop_creation_generate
mop_creation_refine
mop_creation_get
mop_creation_latest
mop_creation_effective_config
```

The MCP surface is intended for Codex and other agents to request generation, retrieve artifacts, and refine documents without bypassing the governed evidence boundaries.

## 9. Configuration

```yaml
agent:
  name: bosgenesis-mop-creation-agent
  mode: on_demand
  source_namespace: bosgenesis
  local_storage_enabled: true
  local_storage_path: /data/mops
  default_generation_mode: platform-only
  public_repositories_only: true

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
  qdrant:
    enabled: true
  redis:
    enabled: false
  pgvector:
    enabled: false

observability:
  langfuse:
    enabled: true
  signoz:
    enabled: true
    otlp_endpoint: http://signoz-otel-collector.signoz:4317

memory:
  langmem:
    enabled: true
    classes:
      - short_term
      - episodic
      - knowledge
  letta:
    enabled: false
    code_available: true

llm:
  standalone_enabled: true
  framework: langchain
  default_model: gpt-4.1-mini
```

## 10. MoP Output Structure

1. Document Header
2. Change Summary
3. Source and Target Namespace Overview
4. Pre-change Checklist
5. Access and Environment Verification
6. Source Namespace Export/Reference Snapshot
7. Target Namespace Preparation
8. Secret Placeholder and Prerequisite Inputs
9. Helm Release Recreation Steps
10. Raw Kubernetes Resource Recreation Steps
11. Application Schema/Topology Recreation Steps, when selected
12. Validation Steps
13. Go/No-Go Decision Points
14. Rollback Procedure
15. Post-change Activities
16. Execution Log
17. Appendix: Generated Manifests, Helm Values, Evidence, and Unknowns

The agent-readable installation guide must include structured metadata, execution phases, dependency graph, command blocks, validation checks, rollback hints, evidence references, confidence markers, and required human inputs.

## 11. Safety Rules

- Never include Secret data.
- Never include secret-like values from environment variables, values files, manifests, schemas, connection strings, or traces.
- Warn that ServiceAccount, Role, RoleBinding, cluster-scoped objects, PVs, CRDs, and node resources are excluded unless future policy allows them.
- Every command must include source or target namespace explicitly.
- All apply commands should recommend `--dry-run=server -o yaml` before real apply.
- Helm commands should include `--dry-run` before real install/upgrade.
- Generated manifests must remove runtime metadata: `uid`, `resourceVersion`, `managedFields`, `creationTimestamp`, `generation`, `ownerReferences`, and `status`.
- Generated manifests must rewrite namespace to target namespace.
- Application mode must recreate schemas/topology only, not data.
- The agent must not execute generated commands.

## 12. Acceptance Criteria

| ID | Criteria |
|---|---|
| AC-1 | API can generate MoP for source `bosgenesis` and target namespace from request. |
| AC-2 | MCP tool can trigger MoP generation for Codex. |
| AC-3 | MoP file is written to local storage. |
| AC-4 | If MongoDB is enabled, MoP is stored in MongoDB. |
| AC-5 | If Qdrant is enabled, MoP chunks are indexed. |
| AC-6 | If Langfuse is enabled, trace is visible. |
| AC-7 | If SigNoz is enabled, OTel spans are visible. |
| AC-8 | MoP includes Helm and raw Kubernetes sections when data exists. |
| AC-9 | MoP excludes or masks sensitive resources. |
| AC-10 | MoP contains copyable commands and expected outputs. |
| AC-11 | Agent does not execute generated commands. |
| AC-12 | Generated manifests use the target namespace and omit runtime metadata. |
| AC-13 | Application mode includes only metadata/schema/topology and no production data. |
| AC-14 | Artifact validation fails publication if secret-like values are detected. |
| AC-15 | Agent-readable Markdown guide is generated alongside the human MoP. |
| AC-16 | Standalone REST mode can use LangChain, configured LLM, and LangMem-backed memory without Codex. |
