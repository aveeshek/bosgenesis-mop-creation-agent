# Documentation Specification

## Intent

`docs/` contains product, architecture, design, algorithm, and output contract specifications for the MoP Creation Agent.

The documentation set must preserve the original product context:

- the agent is non-deterministic by nature and may use an LLM to decide next steps when deterministic evidence is insufficient;
- v1 scope is one namespace, namespace-only, Kubernetes and Helm based, and public repositories only;
- the agent produces a sample-format human MoP artifact, a professional paginated PDF rendered from the resolved generation context, and LLM/agent-readable Markdown installation notes;
- the professional PDF uses the approved 11-section layout, renders execution commands from `machine_execution_plan`, renders validation as human-readable copy-pasteable steps, preserves shell syntax exactly, and groups Appendix A resource snapshots into tables;
- the Markdown installation notes include a canonical `machine_execution_plan` YAML block, and the same plan is also written as a standalone YAML artifact for downstream agents;
- generated artifacts are retrievable through governed preview, full-file download, generated-folder archive, and housekeeping delete APIs;
- the configured source namespace is the startup default, the active source namespace may be switched at runtime through REST/MCP APIs, and `namespace:<active_source_namespace>` is the primary key for agentic memory and session context;
- the agent may read existing vectorized MoP/installation-note references from Qdrant for matching components during generation;
- optional Qdrant insertion of generated MoP artifacts is a separate gated admin flow that requires explicit user confirmation, and generation remains read-only;
- Codex integration is through an on-demand MCP server that supports generation, retrieval, configuration inspection, artifact preview, and artifact cleanup;
- standalone mode is triggered through REST, uses LangGraph/LangChain with a configured LLM profile, and can use optional Phase 11 agentic memory through the LangMem-shaped in-process first/cache adapter, Redis durable short-term memory, PostgreSQL/pgvector durable episodic memory, and disabled future Qdrant/Letta memory adapters;
- Phase 10 LLM reasoning is optional, bounded, redacted, schema-validated, confidence-gated, and advisory only; it must never generate executable manifests/Helm commands as final truth or approve a MoP;
- all actions, tool calls, and reasoning decisions must be traceable in Langfuse, SigNoz/OpenTelemetry, and structured logs;
- future scope includes multi-namespace, cluster-admin add-only scope, custom repositories, Docker image reconstruction hints, and Letta-backed memory.

## Required documents

- Product specification.
- High-level design.
- Low-level design.
- Reasoning algorithm design.
- Human MoP template contract.
- Agent-readable installation notes contract.
- Application-mode schema inference contract.
- Safety and audit contract.
- Sample-derived human MoP template contract.
- Agent-readable Markdown and machine execution plan contract.
- Artifact lifecycle, download/archive, and cleanup contract.
- Professional PDF MoP rendering contract.
- Credentials and service configuration runbook for PostgreSQL, ClickHouse, Redis, Qdrant, Langfuse, SigNoz/OpenTelemetry, MCP endpoints, and LLM endpoints.
- Phase 13.1 validation gates, unit test reports, and code coverage reports.
- Phase 15 deployment guide, sample requests, and release-candidate operational runbook.

## Phase 15 documents

- `DEPLOYMENT.md`: build, deploy, upgrade, rollback, and rollout verification.
- `SAMPLE_REQUESTS.md`: copy-pasteable API requests for health, config,
  generation, artifacts, Qdrant ingestion, and cleanup.
- `RELEASE_CANDIDATE_RUNBOOK.md`: end-to-end release-candidate validation
  procedure for platform-only and application-mode smoke tests.
