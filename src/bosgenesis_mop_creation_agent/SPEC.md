# Package Specification

## Intent

`bosgenesis_mop_creation_agent` implements the MoP Creation Agent runtime.

## Runtime contract

The package must support:

- Codex-integrated on-demand MCP mode for iterative generation and refinement;
- standalone REST-triggered mode using LangGraph/LangChain and a configured LLM profile;
- `platform-only` generation mode;
- `application` generation mode with metadata-only schema/topology output;
- local artifact generation for both the human MoP PDF and Markdown installation notes;
- standalone `machine_execution_plan.yaml` generation for downstream agents;
- artifact preview, full-file download, generated-folder zip archive, and housekeeping deletion APIs;
- optional MongoDB, PostgreSQL, ClickHouse, Redis, pgvector, LangMem, and read-only Qdrant retrieval integrations.

## Architectural rule

Runtime modules must separate:

- deterministic evidence collection, normalization, classification, and validation;
- non-deterministic LLM reasoning;
- sample-template document modeling, PDF rendering, and Markdown notes rendering;
- persistence and read-only prior-reference retrieval;
- observability/audit.

This separation is required so generated artifacts can be traced, reviewed, reproduced from fixed evidence, and validated before publication.

## Safety rule

The package generates procedures. It must not execute generated Helm, Kubernetes, database, cache, or stream commands.

Qdrant is read-only for this package. The package may search for existing vectorized MoP/installation-note references for discovered components, but ingestion/vectorization is owned by a separate agent.

Artifact lifecycle APIs must remain path-guarded to configured local storage and
must never expose or delete files outside the MoP artifact root.
