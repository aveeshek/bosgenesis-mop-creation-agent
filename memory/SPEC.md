# Memory Specification

## Intent

`memory/` defines agentic memory architecture for LangMem-shaped in-process memory and durable backing stores.

## Memory classes

- Short-term memory for active run state, durably persisted in Redis when memory is enabled.
- Episodic memory for prior generation attempts, durably persisted in PostgreSQL/pgvector when configured.
- Knowledge memory for reusable installation patterns, currently held in the LangMem-shaped in-process layer; Qdrant knowledge memory remains disabled future scope.

All memory is keyed by `namespace:<source_namespace>` and must contain only non-secret summaries.

