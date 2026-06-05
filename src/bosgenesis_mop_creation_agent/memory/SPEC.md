# Runtime Memory Specification

## Intent

`memory/` defines runtime access to LangMem-shaped memory and configured backing stores.

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

Implemented Phase 11 adapters:

- LangMem-shaped in-process adapter as the first/cache layer for safe short-term,
  episodic, and knowledge summaries within the running agent process.
- Redis durable short-term memory adapter, enabled by default when memory is
  enabled, storing namespace-scoped JSON memory records in Redis lists.
- PostgreSQL/pgvector durable episodic memory adapter, enabled by default when
  memory is enabled, using `MEMORY_PGVECTOR_DSN` and creating the configured
  memory table if missing.
- Qdrant memory optional adapter placeholder, disabled by default for future
  durable vector/knowledge memory wiring.
- Letta disabled future adapter placeholder that always reports
  `disabled_future_placeholder`.

Implemented durable routing:

- Redis stores short-term run state only. Keys must use
  `<key_prefix>:<namespace_key>:records`, with `key_prefix` defaulting to
  `mop-agent-memory`.
- PostgreSQL/pgvector stores episodic generation memory only through
  `MEMORY_PGVECTOR_DSN`; the adapter may create the `vector` extension when
  available and creates the configured table if missing.
- LangMem-shaped in-process memory is the first/cache layer and can hold safe
  short-term, episodic, and knowledge summaries for the running process.

Future adapter scope:

- Qdrant memory collection for future durable namespace-scoped vector knowledge
  summaries.
- Letta as a future disabled adapter until explicitly enabled by later scope.
- MongoDB or ClickHouse memory adapters only if a future phase accepts them.

## Stored content

Memory may store:

- non-secret run summaries;
- non-secret reasoning summaries;
- artifact metadata;
- accepted installation patterns;
- validation outcomes;
- unknowns and human-input patterns.

The current implementation stores only generated summary records. It must not
store raw manifests, Helm values, prompts, LLM raw responses, database schemas,
environment variables, logs, or raw evidence payloads.

## Runtime behavior

- Memory is disabled by default.
- When enabled, generation reads prior namespace-scoped memory before snapshot
  and reasoning work.
- Prior memory is passed to bounded reasoning as advisory context only.
- Generation writes short-term, episodic, and knowledge summary records after a
  run completes artifact generation.
- Memory read/write status must be logged with `run_id`, `correlation_id`, and
  namespace key.
- API responses must include memory status, read count, and written count.
- Artifact manifests and installation notes must label memory as
  `prior_context_only_not_current_fact`.
- Redis must persist short-term records only.
- PostgreSQL/pgvector must persist episodic records only.

## Safety

Memory must never persist secret values, credentials, production data, table rows, documents, messages, cache values, or raw unredacted evidence.
