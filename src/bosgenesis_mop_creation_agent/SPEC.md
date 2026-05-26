# Package Specification

## Intent

`bosgenesis_mop_creation_agent` will implement the MoP Creation Agent runtime.

## Runtime contract

The package must support:

- Codex-integrated on-demand MCP mode for iterative generation and refinement;
- standalone REST-triggered mode using LangChain and GPT-4.1 mini or configured equivalent model;
- `platform-only` generation mode;
- `application` generation mode with metadata-only schema/topology output;
- local artifact generation for both the human MoP and the agent-readable guide;
- optional MongoDB, Qdrant, PostgreSQL, ClickHouse, Redis, pgvector, and LangMem integrations.

## Architectural rule

Runtime modules must separate:

- deterministic evidence collection, normalization, classification, and validation;
- non-deterministic LLM reasoning;
- artifact rendering;
- persistence/indexing;
- observability/audit.

This separation is required so generated artifacts can be traced, reviewed, reproduced from fixed evidence, and validated before publication.

## Safety rule

The package generates procedures. It must not execute generated Helm, Kubernetes, database, cache, or stream commands.

