# PostgreSQL Memory Specification

## Intent

PostgreSQL/pgvector is the implemented durable backend for episodic generation memory when `MEMORY_PGVECTOR_DSN` is configured.

## Boundary

Stored data must be redacted and reproducible. The memory adapter stores only `episodic` summary records in the configured table, default `mop_agent_memory`, and never stores raw manifests, Helm values, prompts, LLM raw responses, rows, documents, messages, cache values, or credentials.

