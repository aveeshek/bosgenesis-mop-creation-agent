# Runtime Memory Specification

## Intent

`memory/` defines runtime access to LangMem-backed memory and optional backing stores.

## Memory classes

- Short-term run memory.
- Episodic memory for prior MoP generation attempts.
- Knowledge memory for durable installation patterns, decisions, and safe template guidance.

## Backing stores

Future adapters may include:

- Redis for short-term run state, cache, and idempotency locks.
- PostgreSQL or pgvector for metadata and semantic search.
- MongoDB for flexible non-secret episodic records.
- ClickHouse for analytical run events.
- LangMem as the abstraction layer.
- Letta as future disabled adapter until explicitly enabled by later scope.

## Stored content

Memory may store:

- non-secret run summaries;
- non-secret reasoning summaries;
- artifact metadata;
- accepted installation patterns;
- validation outcomes;
- unknowns and human-input patterns.

## Safety

Memory must never persist secret values, credentials, production data, table rows, documents, messages, cache values, or raw unredacted evidence.

