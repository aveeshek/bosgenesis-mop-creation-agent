# Runtime Memory Specification

## Intent

`memory/` defines runtime access to LangMem-backed memory and optional backing stores.

## Memory classes

- Short-term run memory.
- Episodic memory for prior MoP generation attempts.
- Knowledge memory for durable installation patterns, decisions, and safe template guidance.

## Namespace identity

The active source namespace is the primary key for agentic memory and session
context. Memory implementations must use:

```text
namespace:<active_source_namespace>
```

as the namespace-scoped `memory_primary_key` and `session_context_key`.

The active namespace defaults from `agent.source_namespace` and may be switched
at runtime through governed REST/MCP namespace APIs. A per-request
`source_namespace` override applies only to that run and does not mutate the
active runtime namespace.

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
